import math
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class IntradaySignal:
    symbol: str
    score: float
    reason: str
    return_5m_percent: float
    return_15m_percent: float
    volume_ratio: float
    vwap_deviation_percent: float
    spread_percent: float
    event_triggered: bool


@dataclass(frozen=True)
class IntradaySignalDiagnostic:
    symbol: str
    outcome: str
    detail: str


@dataclass(frozen=True)
class IntradaySelectionResult:
    signals: list[IntradaySignal]
    diagnostics: list[IntradaySignalDiagnostic]


class IntradaySignalSelector:
    """Deterministic intraday event trigger over 1-minute candles/orderbook.

    Pure Python: no env, DB, or network access. The caller (MarketDataClient)
    passes in `observed_at` -- its own UTC wall-clock time at fetch time -- and
    every other timestamp in the payload is validated against it. This module
    never reads the system clock itself. Ranks LLM-review candidates from
    precomputed signal payloads; it never decides BUY/SELL itself.
    """

    _RETURN_TRIGGER_PERCENT = 0.5
    _VOLUME_RATIO_TRIGGER = 2.0
    _MAX_SPREAD_PERCENT = 1.0
    _MIN_CANDLES_REQUIRED = 16

    # 1-minute candles are expected back-to-back. Anything looser than these
    # tolerances usually means a session boundary (previous day's closing
    # candles spliced against today's opening candle) or a stalled feed, not
    # a real intraday move -- treat it as missing data, not a signal.
    _MAX_CANDLE_GAP_SECONDS = 150
    _MAX_REFERENCE_GAP_SECONDS = 150
    # How old price/orderbook/candle timestamps may be relative to observed_at.
    # The 1m candle feed from Toss runs measurably behind the current-price
    # quote feed (quotes land ~1s stale in practice; candles were observed
    # missing the old 180s bar on nearly every cycle all trading day on
    # 2026-08-25, starving the LLM of candidates for 12 days straight -- see
    # docs/plans -- the candle feed just isn't as close to real-time as the
    # quote feed, not a sign of bad data). Widened to fit that real latency;
    # revisit with a measured value once the vendor's actual candle delay is
    # confirmed over a live session.
    _MAX_LATEST_CANDLE_AGE_SECONDS = 600
    _MAX_QUOTE_AGE_SECONDS = 120
    # Explicit bound on how far apart the three independent data sources
    # (price quote, orderbook, latest candle) may be from *each other* --
    # each can individually pass its own observed_at age check while still
    # collectively describing different moments (e.g. a candle near its
    # 600s limit and a quote near its 120s limit could otherwise be ~700s
    # apart). This closes that gap with one explicit, tighter constant. Must
    # stay >= _MAX_LATEST_CANDLE_AGE_SECONDS or it becomes the new bottleneck
    # given the quote/candle latency gap above.
    _MAX_SOURCE_SKEW_SECONDS = 600
    # Small clock-skew allowance -- anything claiming to be further in the
    # future than this relative to observed_at is treated as corrupt data,
    # not a legitimate quote.
    _FUTURE_TOLERANCE_SECONDS = 5

    _TRADING_TIMEZONE = ZoneInfo("Asia/Seoul")

    _OPEN_KEYS = ("openPrice", "open_price", "open")
    _CLOSE_KEYS = ("closePrice", "close_price", "close")
    _HIGH_KEYS = ("highPrice", "high_price", "high")
    _LOW_KEYS = ("lowPrice", "low_price", "low")
    _VOLUME_KEYS = ("volume", "tradingVolume", "accumulatedTradingVolume")

    def __init__(self, max_candidates: int = 3):
        if max_candidates < 1:
            raise ValueError("max_candidates must be positive.")
        self.max_candidates = max_candidates

    def select(
        self,
        signals_by_symbol: dict[str, dict[str, Any]],
        candidates: list[str],
    ) -> list[IntradaySignal]:
        return self.select_with_diagnostics(signals_by_symbol, candidates).signals

    def select_with_diagnostics(
        self,
        signals_by_symbol: dict[str, dict[str, Any]],
        candidates: list[str],
    ) -> IntradaySelectionResult:
        if not isinstance(signals_by_symbol, dict) or not isinstance(candidates, list):
            return IntradaySelectionResult(signals=[], diagnostics=[])

        built: list[IntradaySignal] = []
        diagnostics: list[IntradaySignalDiagnostic] = []
        for symbol in candidates:
            if not isinstance(symbol, str):
                continue
            payload = signals_by_symbol.get(symbol)
            if not isinstance(payload, dict):
                diagnostics.append(
                    IntradaySignalDiagnostic(
                        symbol=symbol,
                        outcome="MISSING_CONTEXT",
                        detail="Intraday context was missing or malformed.",
                    )
                )
                continue
            signal, rejection = self._evaluate_signal(symbol, payload)
            if signal is not None:
                built.append(signal)
                diagnostics.append(
                    IntradaySignalDiagnostic(
                        symbol=symbol,
                        outcome="TRIGGERED" if signal.event_triggered else "NO_EVENT",
                        detail=signal.reason,
                    )
                )
            else:
                diagnostics.append(
                    IntradaySignalDiagnostic(
                        symbol=symbol,
                        outcome=rejection or "INVALID_SIGNAL",
                        detail="Signal validation failed closed.",
                    )
                )

        triggered = [signal for signal in built if signal.event_triggered]
        triggered.sort(key=lambda item: item.score, reverse=True)
        return IntradaySelectionResult(
            signals=triggered[: self.max_candidates],
            diagnostics=diagnostics,
        )

    def _build_signal(self, symbol: str, payload: dict[str, Any]) -> IntradaySignal | None:
        signal, _rejection = self._evaluate_signal(symbol, payload)
        return signal

    def _evaluate_signal(
        self,
        symbol: str,
        payload: dict[str, Any],
    ) -> tuple[IntradaySignal | None, str | None]:
        price = self._to_float(payload.get("price"))
        if price is None or price <= 0:
            return None, "INVALID_PRICE"

        # observed_at is the caller's UTC fetch-time anchor. Every other
        # timestamp below is checked against it, both for being too old and
        # for claiming to be in the future -- either one means the data can't
        # be trusted enough to act on. A missing observed_at means we have no
        # anchor at all, so fail closed rather than silently skipping checks.
        observed_at = self._parse_timestamp(payload.get("observed_at"))
        if observed_at is None:
            return None, "INVALID_OBSERVED_AT"

        price_ts, price_ts_rejection = self._timestamp_result(
            payload.get("price_timestamp"),
            observed_at,
            self._MAX_QUOTE_AGE_SECONDS,
            source="PRICE",
        )
        if price_ts is None:
            return None, price_ts_rejection

        orderbook_ts, orderbook_ts_rejection = self._timestamp_result(
            payload.get("orderbook_timestamp"),
            observed_at,
            self._MAX_QUOTE_AGE_SECONDS,
            source="ORDERBOOK",
        )
        if orderbook_ts is None:
            return None, orderbook_ts_rejection

        candles = self._sorted_candles(payload.get("candles"))
        if candles is None:
            return None, "INVALID_CANDLE_SERIES"

        latest_ts = candles[-1][0]
        if not self._within_tolerance(latest_ts, observed_at, self._MAX_LATEST_CANDLE_AGE_SECONDS):
            return None, "STALE_OR_FUTURE_CANDLE"

        source_timestamps = (price_ts, orderbook_ts, latest_ts)
        if max(source_timestamps) - min(source_timestamps) > self._MAX_SOURCE_SKEW_SECONDS:
            # Each source can individually be "recent enough" relative to
            # observed_at yet still disagree with each other -- e.g. a quote
            # from just now paired with a candle feed that stalled a few
            # minutes ago. Require them to describe roughly the same moment.
            return None, "SOURCE_TIMESTAMP_SKEW"

        return_5m = self._return_percent(candles, latest_ts, price, minutes=5)
        return_15m = self._return_percent(candles, latest_ts, price, minutes=15)
        if return_5m is None or return_15m is None:
            return None, "INVALID_RETURN_WINDOW"

        volume_ratio = self._volume_ratio(candles)
        vwap_deviation = self._vwap_deviation_percent(candles, price)

        spread_percent = self._spread_percent(payload.get("bids"), payload.get("asks"))
        if spread_percent is None:
            # Missing, empty, malformed, or crossed orderbook: never fabricate
            # a candidate on an unknown spread.
            return None, "INVALID_ORDERBOOK"

        triggered_by_move = (
            abs(return_5m) >= self._RETURN_TRIGGER_PERCENT
            or abs(return_15m) >= self._RETURN_TRIGGER_PERCENT
        )
        triggered_by_volume = volume_ratio >= self._VOLUME_RATIO_TRIGGER
        spread_ok = spread_percent <= self._MAX_SPREAD_PERCENT
        event_triggered = bool((triggered_by_move or triggered_by_volume) and spread_ok)

        score = (
            abs(return_5m) * 2.0
            + abs(return_15m)
            + max(volume_ratio - 1.0, 0.0) * 1.5
            - spread_percent * 0.5
        )
        if not math.isfinite(score):
            return None, "INVALID_SCORE"

        return (
            IntradaySignal(
                symbol=symbol,
                score=round(score, 4),
                reason=self._reason(
                    return_5m=return_5m,
                    return_15m=return_15m,
                    volume_ratio=volume_ratio,
                    spread_percent=spread_percent,
                    triggered_by_move=triggered_by_move,
                    triggered_by_volume=triggered_by_volume,
                    spread_ok=spread_ok,
                ),
                return_5m_percent=round(return_5m, 4),
                return_15m_percent=round(return_15m, 4),
                volume_ratio=round(volume_ratio, 4),
                vwap_deviation_percent=round(vwap_deviation, 4),
                spread_percent=round(spread_percent, 4),
                event_triggered=event_triggered,
            ),
            None,
        )

    def _sorted_candles(self, raw_candles: Any) -> list[tuple[float, float, float, float]] | None:
        if not isinstance(raw_candles, list) or not raw_candles:
            return None

        parsed: list[tuple[float, float, float, float]] = []
        for candle in raw_candles:
            validated = self._validate_candle(candle)
            if validated is None:
                # One malformed/inconsistent candle taints the whole series --
                # a feed that produced garbage once can't be trusted to have
                # produced clean data everywhere else, so fail the whole
                # symbol rather than silently dropping just that candle.
                return None
            parsed.append(validated)

        if len(parsed) < self._MIN_CANDLES_REQUIRED:
            return None

        # Accept candles in either newest-first or oldest-first order: sort by
        # timestamp so downstream lookups don't depend on input order.
        parsed.sort(key=lambda item: item[0])

        # Keep only candles from the same KST trading day as the newest one.
        # Without this, a shortlist fetch that happens to include the tail of
        # yesterday's session (e.g. 15:16-15:30) alongside this morning's
        # first candle would compute a "5-minute return" across an overnight
        # gap and mistake the open-vs-previous-close jump for an intraday move.
        latest_date = self._kst_date(parsed[-1][0])
        same_day = [item for item in parsed if self._kst_date(item[0]) == latest_date]
        if len(same_day) < self._MIN_CANDLES_REQUIRED:
            return None

        for previous_candle, current_candle in zip(same_day, same_day[1:]):
            if current_candle[0] - previous_candle[0] > self._MAX_CANDLE_GAP_SECONDS:
                return None

        return same_day

    def _validate_candle(self, candle: Any) -> tuple[float, float, float, float] | None:
        """Parse and strictly validate one OHLCV candle.

        Every field must be present and finite, prices must be positive,
        volume non-negative, and the OHLC relationship internally consistent
        (high is the max, low is the min). Any violation returns None so the
        caller can fail the whole symbol rather than compute a signal from a
        candle series with one bad bar spliced into it.
        """
        if not isinstance(candle, dict):
            return None

        timestamp = self._parse_timestamp(candle.get("timestamp"))
        if timestamp is None:
            return None

        open_price = self._first_float(candle, self._OPEN_KEYS)
        high = self._first_float(candle, self._HIGH_KEYS)
        low = self._first_float(candle, self._LOW_KEYS)
        close = self._first_float(candle, self._CLOSE_KEYS)
        volume = self._first_float(candle, self._VOLUME_KEYS)
        if None in (open_price, high, low, close, volume):
            return None

        if open_price <= 0 or high <= 0 or low <= 0 or close <= 0:
            return None
        if volume < 0:
            return None
        if high < max(open_price, close):
            return None
        if low > min(open_price, close):
            return None
        if high < low:
            return None

        typical_price = (high + low + close) / 3.0
        return (timestamp, close, volume, typical_price)

    @staticmethod
    def _kst_date(timestamp: float):
        return datetime.fromtimestamp(timestamp, tz=IntradaySignalSelector._TRADING_TIMEZONE).date()

    def _timestamp_result(
        self,
        value: Any,
        observed_at: float,
        max_age_seconds: float,
        *,
        source: str,
    ) -> tuple[float | None, str | None]:
        parsed = self._parse_timestamp(value)
        if parsed is None:
            return None, f"INVALID_{source}_TIMESTAMP"
        if not self._within_tolerance(parsed, observed_at, max_age_seconds):
            return None, f"STALE_OR_FUTURE_{source}"
        return parsed, None

    @staticmethod
    def _within_tolerance(timestamp: float, observed_at: float, max_age_seconds: float) -> bool:
        if timestamp - observed_at > IntradaySignalSelector._FUTURE_TOLERANCE_SECONDS:
            return False
        if observed_at - timestamp > max_age_seconds:
            return False
        return True

    @staticmethod
    def _return_percent(
        candles: list[tuple[float, float, float, float]],
        latest_ts: float,
        current_price: float,
        *,
        minutes: int,
    ) -> float | None:
        cutoff = latest_ts - minutes * 60
        reference_close: float | None = None
        reference_ts: float | None = None
        for timestamp, close, _volume, _typical in candles:
            if timestamp <= cutoff:
                reference_close = close
                reference_ts = timestamp
            else:
                break
        if reference_close is None or reference_close <= 0 or reference_ts is None:
            return None
        if cutoff - reference_ts > IntradaySignalSelector._MAX_REFERENCE_GAP_SECONDS:
            # The closest candle at/before the target time is too far from it
            # (a data gap) -- don't read a return out of a hole in the feed.
            return None
        value = (current_price - reference_close) / reference_close * 100.0
        return value if math.isfinite(value) else None

    @staticmethod
    def _volume_ratio(candles: list[tuple[float, float, float, float]]) -> float:
        if len(candles) < 2:
            return 0.0
        latest_volume = candles[-1][2]
        previous_volumes = [item[2] for item in candles[:-1]]
        avg_previous = sum(previous_volumes) / len(previous_volumes) if previous_volumes else 0.0
        if avg_previous <= 0:
            return 0.0
        ratio = latest_volume / avg_previous
        return ratio if math.isfinite(ratio) else 0.0

    @staticmethod
    def _vwap_deviation_percent(
        candles: list[tuple[float, float, float, float]],
        current_price: float,
    ) -> float:
        total_volume = sum(item[2] for item in candles)
        if total_volume <= 0:
            return 0.0
        vwap = sum(item[3] * item[2] for item in candles) / total_volume
        if vwap <= 0:
            return 0.0
        deviation = (current_price - vwap) / vwap * 100.0
        return deviation if math.isfinite(deviation) else 0.0

    def _spread_percent(self, bids: Any, asks: Any) -> float | None:
        best_bid = self._best_price(bids, pick="max")
        best_ask = self._best_price(asks, pick="min")
        if best_bid is None or best_ask is None:
            return None
        if best_ask < best_bid:
            # Crossed/invalid book -- never trust it enough to compute a spread.
            return None
        mid = (best_bid + best_ask) / 2.0
        if mid <= 0:
            return None
        spread = (best_ask - best_bid) / mid * 100.0
        return spread if math.isfinite(spread) else None

    @staticmethod
    def _best_price(levels: Any, *, pick: str) -> float | None:
        if not isinstance(levels, list) or not levels:
            return None
        prices = []
        for level in levels:
            if not isinstance(level, dict):
                continue
            price = IntradaySignalSelector._to_float(level.get("price"))
            if price is not None and price > 0:
                prices.append(price)
        if not prices:
            return None
        return max(prices) if pick == "max" else min(prices)

    @staticmethod
    def _reason(
        *,
        return_5m: float,
        return_15m: float,
        volume_ratio: float,
        spread_percent: float,
        triggered_by_move: bool,
        triggered_by_volume: bool,
        spread_ok: bool,
    ) -> str:
        if not spread_ok:
            return (
                f"Spread {spread_percent:.2f}% exceeds the "
                f"{IntradaySignalSelector._MAX_SPREAD_PERCENT:.2f}% cap; no event."
            )
        parts = []
        if triggered_by_move:
            parts.append(f"5m/15m return {return_5m:.2f}%/{return_15m:.2f}%")
        if triggered_by_volume:
            parts.append(f"volume {volume_ratio:.2f}x average")
        if not parts:
            return "No qualifying intraday move or volume expansion."
        return "; ".join(parts) + f" (spread {spread_percent:.2f}%)"

    @staticmethod
    def _parse_timestamp(value: Any) -> float | None:
        if value is None:
            return None
        if isinstance(value, bool):
            return None
        if isinstance(value, (int, float)):
            return float(value) if math.isfinite(value) else None
        text = str(value).strip()
        if not text:
            return None
        try:
            return datetime.fromisoformat(text).timestamp()
        except ValueError:
            pass
        try:
            parsed = float(text)
        except ValueError:
            return None
        return parsed if math.isfinite(parsed) else None

    @staticmethod
    def _to_float(value: Any) -> float | None:
        if value is None:
            return None
        if isinstance(value, bool):
            return None
        try:
            parsed = float(str(value).replace(",", "").replace("%", ""))
        except (TypeError, ValueError):
            return None
        return parsed if math.isfinite(parsed) else None

    @staticmethod
    def _first_float(data: dict[str, Any], keys: tuple[str, ...]) -> float | None:
        for key in keys:
            value = IntradaySignalSelector._to_float(data.get(key))
            if value is not None:
                return value
        return None
