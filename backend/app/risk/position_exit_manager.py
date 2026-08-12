import math
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from app.config import Settings, get_settings


@dataclass(frozen=True)
class PositionExitSignal:
    symbol: str
    reason_code: str
    reason: str
    current_price: float
    pnl_percent: float
    peak_price: float
    drawdown_from_peak_percent: float
    holding_trading_days: int


class PositionExitManager:
    """Deterministic exit policy for bot-owned paper positions."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.market_timezone = ZoneInfo(self.settings.agent_market_timezone)
        self.closed_dates = set(self.settings.agent_market_closed_dates)

    def evaluate(
        self,
        position: Any,
        *,
        current_price: float,
        peak_price: float,
        observed_at: datetime,
    ) -> PositionExitSignal | None:
        avg_buy_price = self._finite_float(getattr(position, "avg_buy_price", None))
        quantity = self._finite_float(getattr(position, "quantity", None))
        current = self._finite_float(current_price)
        peak = self._finite_float(peak_price)
        opened_at = getattr(position, "created_at", None)
        symbol = str(getattr(position, "symbol", "")).upper()
        if (
            not symbol
            or avg_buy_price is None
            or avg_buy_price <= 0
            or quantity is None
            or quantity <= 0
            or current is None
            or current <= 0
            or peak is None
            or peak <= 0
            or not isinstance(opened_at, datetime)
        ):
            return None

        peak = max(peak, current, avg_buy_price)
        pnl_percent = (current - avg_buy_price) / avg_buy_price * 100
        peak_gain_percent = (peak - avg_buy_price) / avg_buy_price * 100
        drawdown_percent = (peak - current) / peak * 100
        holding_days = self._trading_days_between(opened_at, observed_at)

        stop_loss = self.settings.position_stop_loss_percent_safe
        if stop_loss is not None and pnl_percent <= -stop_loss:
            return self._signal(
                symbol,
                "STOP_LOSS",
                f"Position loss {pnl_percent:.2f}% reached the -{stop_loss:.2f}% stop.",
                current,
                pnl_percent,
                peak,
                drawdown_percent,
                holding_days,
            )

        take_profit = self.settings.position_take_profit_percent_safe
        if take_profit is not None and pnl_percent >= take_profit:
            return self._signal(
                symbol,
                "TAKE_PROFIT",
                f"Position gain {pnl_percent:.2f}% reached the +{take_profit:.2f}% target.",
                current,
                pnl_percent,
                peak,
                drawdown_percent,
                holding_days,
            )

        activation = self.settings.position_trailing_activation_percent_safe
        distance = self.settings.position_trailing_distance_percent_safe
        if (
            self.settings.position_trailing_stop_enabled
            and activation is not None
            and distance is not None
            and peak_gain_percent >= activation
            and drawdown_percent >= distance
        ):
            return self._signal(
                symbol,
                "TRAILING_STOP",
                (
                    f"Peak gain reached {peak_gain_percent:.2f}% and price retreated "
                    f"{drawdown_percent:.2f}% from the peak."
                ),
                current,
                pnl_percent,
                peak,
                drawdown_percent,
                holding_days,
            )

        max_holding_days = self.settings.position_max_holding_trading_days_safe
        if max_holding_days is not None and holding_days >= max_holding_days:
            return self._signal(
                symbol,
                "MAX_HOLDING_PERIOD",
                f"Position reached the {max_holding_days}-trading-day holding limit.",
                current,
                pnl_percent,
                peak,
                drawdown_percent,
                holding_days,
            )
        return None

    def _trading_days_between(self, opened_at: datetime, observed_at: datetime) -> int:
        start = self._local_date(opened_at)
        end = self._local_date(observed_at)
        if end <= start:
            return 0
        days = 0
        cursor = date.fromordinal(start.toordinal() + 1)
        while cursor <= end:
            if cursor.weekday() < 5 and cursor.isoformat() not in self.closed_dates:
                days += 1
            cursor = date.fromordinal(cursor.toordinal() + 1)
        return days

    def _local_date(self, value: datetime) -> date:
        if value.tzinfo is None:
            value = value.replace(tzinfo=ZoneInfo("UTC"))
        return value.astimezone(self.market_timezone).date()

    @staticmethod
    def _signal(
        symbol: str,
        reason_code: str,
        reason: str,
        current_price: float,
        pnl_percent: float,
        peak_price: float,
        drawdown_percent: float,
        holding_days: int,
    ) -> PositionExitSignal:
        return PositionExitSignal(
            symbol=symbol,
            reason_code=reason_code,
            reason=reason,
            current_price=round(current_price, 8),
            pnl_percent=round(pnl_percent, 4),
            peak_price=round(peak_price, 8),
            drawdown_from_peak_percent=round(drawdown_percent, 4),
            holding_trading_days=holding_days,
        )

    @staticmethod
    def _finite_float(value: Any) -> float | None:
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return None
        return parsed if math.isfinite(parsed) else None
