import math
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from app.clients.toss_client import TossClient
from app.config import Settings, get_settings
from app.utils.symbols import symbol_sector


@dataclass(frozen=True)
class MarketDataResult:
    success: bool
    status: str
    message: str
    snapshots: list[dict] = field(default_factory=list)


class MarketDataClient:
    """Read-only KRX quotes and candles from the Toss Securities Open API."""

    provider_name = "toss_securities"

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.toss_client = TossClient(self.settings)
        self._daily_reference_cache: dict[str, tuple[str, float, float]] = {}
        self._last_chart_request_at = 0.0

    def get_market_snapshots(self, symbols: list[str]) -> MarketDataResult:
        if not symbols:
            return MarketDataResult(success=True, status="OK", message="No symbols requested.", snapshots=[])

        if not self.settings.toss_market_data_ready:
            return MarketDataResult(
                success=False,
                status="NOT_CONFIGURED",
                message=(
                    "Toss market data endpoints are not ready. Check TOSS_API_KEY/TOSS_SECRET_KEY, "
                    "TOSS_TOKEN_PATH, TOSS_CANDLES_PATH, TOSS_PRICES_PATH, and TOSS_ORDERBOOK_PATH."
                ),
                snapshots=[],
            )

        if self.settings.intraday_signals_enabled:
            realtime_result = self._get_realtime_snapshots(symbols)
            if realtime_result.success:
                return realtime_result
        return self._get_daily_snapshots(symbols)

    def get_intraday_context(self, symbols: list[str]) -> dict[str, dict]:
        """Fetch 1-minute candles and orderbook only for a small shortlist."""
        contexts: dict[str, dict] = {}
        for raw_symbol in symbols[: self.settings.intraday_shortlist_size_safe]:
            symbol = raw_symbol.strip().upper()
            self._pace_chart_request()
            candle_response = self.toss_client.get_intraday_candles(
                symbol,
                count=self.settings.intraday_candle_count_safe,
            )
            orderbook_response = self.toss_client.get_orderbook(symbol)
            # Captured right after this symbol's fetches complete -- the
            # selector validates every other timestamp in the payload
            # (price/orderbook/candle) against this anchor, so it must be a
            # real wall-clock read, not a value that could be missing/forged.
            observed_at = datetime.now(timezone.utc).isoformat()
            if candle_response.get("success"):
                candles = self._extract_candles(candle_response.get("data") or {})
                if candles:
                    orderbook = orderbook_response.get("data") if orderbook_response.get("success") else {}
                    contexts[symbol] = {
                        "candles": candles,
                        "bids": self._extract_book_side(orderbook or {}, "bids"),
                        "asks": self._extract_book_side(orderbook or {}, "asks"),
                        "orderbook_timestamp": self._extract_timestamp(orderbook or {}),
                        "observed_at": observed_at,
                        "source": self.provider_name,
                    }
        return contexts

    def _get_realtime_snapshots(self, symbols: list[str]) -> MarketDataResult:
        normalized = [symbol.strip().upper() for symbol in symbols if symbol.strip()]
        response = self.toss_client.get_current_prices(normalized)
        if not response.get("success"):
            return MarketDataResult(
                success=False,
                status="FETCH_FAILED",
                message=response.get("message", "Toss current-price request failed."),
                snapshots=[],
            )

        quotes = self._extract_records(response.get("data") or {})
        quote_by_symbol = {
            str(item.get("symbol") or item.get("stockCode") or "").upper(): item
            for item in quotes
            if isinstance(item, dict)
        }
        snapshots: list[dict] = []
        errors: list[str] = []
        for symbol in normalized:
            quote = quote_by_symbol.get(symbol)
            price = self._first_float(quote or {}, ["lastPrice", "last_price", "price", "closePrice"])
            if not quote or price is None or price <= 0:
                errors.append(f"{symbol}: current price missing")
                continue
            reference = self._daily_reference(symbol)
            previous_close, reference_volume = reference if reference else (price, 1.0)
            change_percent = round((price - previous_close) / previous_close * 100, 4) if previous_close else 0.0
            snapshots.append(
                {
                    "symbol": symbol,
                    "price": price,
                    "change_percent": change_percent,
                    "volume": max(reference_volume, 1.0),
                    "sector": symbol_sector(symbol) or "unknown",
                    "extra_json": {
                        "source": self.provider_name,
                        "price_mode": "current_price",
                        "price_timestamp": quote.get("timestamp"),
                        "previous_close": previous_close,
                    },
                }
            )

        if not snapshots:
            return MarketDataResult(
                success=False,
                status="FETCH_FAILED",
                message="; ".join(errors) or "No current prices could be parsed.",
                snapshots=[],
            )
        message = f"Fetched {len(snapshots)}/{len(normalized)} symbols from Toss current prices."
        if errors:
            message = f"{message} Errors: {'; '.join(errors)}"
        return MarketDataResult(success=True, status="OK", message=message, snapshots=snapshots)

    def _daily_reference(self, symbol: str) -> tuple[float, float] | None:
        market_date = datetime.now(ZoneInfo(self.settings.agent_market_timezone)).date().isoformat()
        cached = self._daily_reference_cache.get(symbol)
        if cached and cached[0] == market_date:
            return cached[1], cached[2]

        self._pace_chart_request()
        response = self.toss_client.get_daily_candles(symbol, count=2)
        if not response.get("success"):
            return (cached[1], cached[2]) if cached else None
        candles = sorted(
            self._extract_candles(response.get("data") or {}),
            key=lambda item: item.get("timestamp") or "",
            reverse=True,
        )
        if not candles:
            return None
        newest = candles[0]
        newest_date = str(newest.get("timestamp") or "")[:10]
        reference_candle = candles[1] if newest_date == market_date and len(candles) >= 2 else newest
        previous_close = self._first_float(reference_candle, ["closePrice", "close_price", "close"])
        volume = self._first_float(newest, ["volume", "tradingVolume", "accumulatedTradingVolume"]) or 1.0
        if previous_close is None or previous_close <= 0:
            return None
        self._daily_reference_cache[symbol] = (market_date, previous_close, volume)
        return previous_close, volume

    def _pace_chart_request(self) -> None:
        # Toss documents MARKET_DATA_CHART separately at 5 TPS.
        elapsed = time.monotonic() - self._last_chart_request_at
        wait_seconds = max(0.21 - elapsed, 0)
        if wait_seconds:
            time.sleep(wait_seconds)
        self._last_chart_request_at = time.monotonic()

    def _get_daily_snapshots(self, symbols: list[str]) -> MarketDataResult:
        snapshots: list[dict] = []
        errors: list[str] = []
        for symbol in symbols:
            self._pace_chart_request()
            response = self.toss_client.get_daily_candles(symbol, count=2)
            if not response.get("success"):
                errors.append(f"{symbol}: {response.get('message', 'unknown error')}")
                continue
            snapshot = self._parse_daily_snapshot(symbol, response.get("data") or {})
            if snapshot:
                snapshots.append(snapshot)
            else:
                errors.append(f"{symbol}: response did not contain usable candles.")

        if not snapshots:
            return MarketDataResult(
                success=False,
                status="FETCH_FAILED",
                message="; ".join(errors) or "No snapshots could be fetched.",
                snapshots=[],
            )
        message = f"Fetched {len(snapshots)}/{len(symbols)} symbols from Toss daily candles."
        if errors:
            message = f"{message} Errors: {'; '.join(errors)}"
        return MarketDataResult(success=True, status="OK", message=message, snapshots=snapshots)

    def _parse_daily_snapshot(self, symbol: str, data: dict) -> dict | None:
        candles = sorted(
            self._extract_candles(data),
            key=lambda item: item.get("timestamp") or "",
            reverse=True,
        )
        if not candles:
            return None
        latest = candles[0]
        price = self._first_float(latest, ["closePrice", "close_price", "close"])
        if price is None or price <= 0:
            return None
        volume = self._first_float(latest, ["volume", "tradingVolume", "accumulatedTradingVolume"]) or 0.0
        change_percent = 0.0
        if len(candles) >= 2:
            previous_close = self._first_float(candles[1], ["closePrice", "close_price", "close"])
            if previous_close:
                change_percent = round((price - previous_close) / previous_close * 100, 4)
        return {
            "symbol": symbol.upper(),
            "price": price,
            "change_percent": change_percent,
            "volume": volume,
            "sector": symbol_sector(symbol) or "unknown",
            "extra_json": {"source": self.provider_name, "price_mode": "daily_candle", "raw": data},
        }

    @staticmethod
    def _extract_records(data: dict) -> list[dict]:
        for key in ["result", "prices", "data"]:
            value = data.get(key)
            if isinstance(value, list):
                return value
            if isinstance(value, dict):
                nested = MarketDataClient._extract_records(value)
                if nested:
                    return nested
        return []

    @staticmethod
    def _extract_candles(data: dict) -> list[dict]:
        for key in ["candles", "result", "data"]:
            value = data.get(key)
            if isinstance(value, list):
                return value
            if isinstance(value, dict):
                nested = MarketDataClient._extract_candles(value)
                if nested:
                    return nested
        return []

    @staticmethod
    def _extract_book_side(data: dict, side: str) -> list[dict]:
        value = data.get(side)
        if isinstance(value, list):
            return value
        for key in ["result", "orderbook", "data"]:
            nested = data.get(key)
            if isinstance(nested, dict):
                found = MarketDataClient._extract_book_side(nested, side)
                if found:
                    return found
        return []

    @staticmethod
    def _extract_timestamp(data: dict) -> str | None:
        for key in ["timestamp", "time", "quoteTime", "orderbookTimestamp"]:
            value = data.get(key)
            if value is not None:
                return value
        for key in ["result", "orderbook", "data"]:
            nested = data.get(key)
            if isinstance(nested, dict):
                found = MarketDataClient._extract_timestamp(nested)
                if found:
                    return found
        return None

    @staticmethod
    def _first_float(data: dict, keys: list[str]) -> float | None:
        for key in keys:
            value = data.get(key)
            if value is None:
                continue
            try:
                parsed = float(str(value).replace(",", "").replace("%", ""))
            except (TypeError, ValueError):
                continue
            if not math.isfinite(parsed):
                # NaN/Infinity is corrupt data, not a usable fallback -- keep
                # trying the remaining candidate keys instead of returning it.
                continue
            return parsed
        return None
