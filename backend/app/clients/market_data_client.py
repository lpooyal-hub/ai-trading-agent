from dataclasses import dataclass, field

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
    """Real KRX market data via the Toss Securities Open API (read-only,
    account-independent daily candles -- see TossClient.get_daily_candles()).

    Toss has no single "current price + change% + volume" endpoint
    (/api/v1/prices only returns lastPrice), so price/change_percent/volume
    are derived from the latest 2 daily candles: price and volume come from
    the most recent candle, change_percent is computed against the prior
    candle's close. Confirmed against the real canonical OpenAPI spec
    (https://openapi.tossinvest.com/openapi-docs/latest/openapi.json), not
    guessed from third-party doc reproductions.
    """

    provider_name = "toss_securities"

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.toss_client = TossClient(self.settings)

    def get_market_snapshots(self, symbols: list[str]) -> MarketDataResult:
        if not symbols:
            return MarketDataResult(success=True, status="OK", message="No symbols requested.", snapshots=[])

        if not self.settings.toss_market_data_ready:
            return MarketDataResult(
                success=False,
                status="NOT_CONFIGURED",
                message=(
                    "Toss market data endpoint is not ready. Check TOSS_API_KEY/TOSS_SECRET_KEY, "
                    "TOSS_TOKEN_PATH, and TOSS_CANDLES_PATH."
                ),
                snapshots=[],
            )

        snapshots: list[dict] = []
        errors: list[str] = []
        for symbol in symbols:
            response = self.toss_client.get_daily_candles(symbol, count=2)
            if not response.get("success"):
                errors.append(f"{symbol}: {response.get('message', 'unknown error')}")
                continue
            snapshot = self._parse_snapshot(symbol, response.get("data") or {})
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

    def _parse_snapshot(self, symbol: str, data: dict) -> dict | None:
        candles = self._extract_candles(data)
        if not candles:
            return None
        # Toss returns candles newest-first (index 0 = today), confirmed by
        # a live call: candles[0]'s timestamp was today's date, candles[1]
        # yesterday's. Sort by timestamp defensively instead of trusting
        # array order, in case that ever changes.
        candles = sorted(candles, key=lambda item: item.get("timestamp") or "", reverse=True)

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
            "extra_json": {"source": self.provider_name, "raw": data},
        }

    @staticmethod
    def _extract_candles(data: dict) -> list[dict]:
        for key in ["candles", "result", "data"]:
            value = data.get(key)
            if isinstance(value, list):
                return value
            if isinstance(value, dict) and isinstance(value.get("candles"), list):
                return value["candles"]
        return []

    @staticmethod
    def _first_float(data: dict, keys: list[str]) -> float | None:
        for key in keys:
            value = data.get(key)
            if value is None:
                continue
            try:
                return float(str(value).replace(",", "").replace("%", ""))
            except (TypeError, ValueError):
                continue
        return None
