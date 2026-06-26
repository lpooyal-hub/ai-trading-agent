from datetime import datetime, time, timezone
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.models import AgentAction, BotPosition, LegacyPosition, OrderStatus, TradeOrder


class RiskManager:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    def validate_decision(
        self,
        decision: Any,
        db: Session,
        available_bot_budget: float | None = None,
        product_name: str | None = None,
        sell_quantity: float | None = None,
    ) -> dict[str, bool | str]:
        symbol = self._read(decision, "symbol", "").upper()
        sector = self._read(decision, "sector", "").lower()
        action = self._read(decision, "action", "")
        amount = float(self._read(decision, "recommended_order_amount", 0) or 0)
        price = float(self._read(decision, "current_price", 0) or 0)
        name = product_name or self._read(decision, "name", symbol)

        if not self.settings.dry_run and not self.settings.live_trading_enabled:
            return self._reject("Live trading is disabled while DRY_RUN is false.")

        if symbol not in self.settings.allowed_symbols:
            return self._reject(f"Symbol {symbol} is outside the active Top 10 universe.")

        if symbol in self.settings.protected_symbols:
            return self._reject(f"Symbol {symbol} is protected and cannot be traded.")

        if sector != self.settings.allowed_sector.lower():
            return self._reject(f"Sector {sector} is not allowed.")

        if self._contains_forbidden_keyword(name):
            return self._reject("Product name contains a forbidden leveraged/inverse keyword.")

        legacy_position = self._get_legacy_position(db, symbol)
        bot_position = self._get_bot_position(db, symbol)
        if legacy_position and not bot_position:
            return self._reject(f"Symbol {symbol} exists only as a protected legacy position.")

        if amount > self.settings.max_order_amount_usd:
            return self._reject("Recommended order amount exceeds MAX_ORDER_AMOUNT_USD.")

        exposure = self.calculate_bot_exposure(db)
        if action == AgentAction.BUY and amount + exposure > self.settings.bot_capital_limit_usd:
            return self._reject("Total bot invested amount would exceed BOT_CAPITAL_LIMIT_USD.")

        budget = (
            available_bot_budget
            if available_bot_budget is not None
            else self.settings.bot_capital_limit_usd - exposure
        )
        if action == AgentAction.BUY and amount > budget:
            return self._reject("Available bot budget is insufficient.")

        if action == AgentAction.BUY and not bot_position:
            open_positions = self.count_open_positions(db)
            if open_positions >= self.settings.max_positions:
                return self._reject("MAX_POSITIONS would be exceeded.")

        if self.count_today_simulated_trades(db) >= self.settings.max_daily_trades:
            return self._reject("MAX_DAILY_TRADES has been reached.")

        if action == AgentAction.SELL:
            owned_quantity = bot_position.quantity if bot_position else 0
            requested_quantity = sell_quantity or self._estimate_quantity(amount, price)
            if requested_quantity > owned_quantity:
                return self._reject("Sell quantity exceeds bot-owned quantity.")

        position_loss_reason = self._position_loss_guardrail_reason(db)
        if position_loss_reason:
            return self._reject(position_loss_reason)

        daily_loss_reason = self._daily_loss_guardrail_reason(db)
        if daily_loss_reason:
            return self._reject(daily_loss_reason)

        return {"approved": True, "reason": "Approved by RiskManager."}

    def calculate_bot_exposure(self, db: Session) -> float:
        exposure = db.query(func.coalesce(func.sum(BotPosition.total_invested_amount), 0)).scalar()
        return float(exposure or 0)

    def count_open_positions(self, db: Session) -> int:
        return (
            db.query(BotPosition)
            .filter(BotPosition.status == "OPEN")
            .count()
        )

    def count_today_simulated_trades(self, db: Session) -> int:
        today_start = datetime.combine(
            datetime.now(timezone.utc).date(),
            time.min,
            tzinfo=timezone.utc,
        ).replace(tzinfo=None)
        return (
            db.query(TradeOrder)
            .filter(TradeOrder.created_at >= today_start)
            .filter(TradeOrder.status == OrderStatus.SIMULATED)
            .count()
        )

    def _get_legacy_position(self, db: Session, symbol: str) -> LegacyPosition | None:
        return (
            db.query(LegacyPosition)
            .filter(LegacyPosition.symbol == symbol)
            .filter(LegacyPosition.is_protected.is_(True))
            .first()
        )

    def _get_bot_position(self, db: Session, symbol: str) -> BotPosition | None:
        return (
            db.query(BotPosition)
            .filter(BotPosition.symbol == symbol)
            .filter(BotPosition.status == "OPEN")
            .first()
        )

    def _contains_forbidden_keyword(self, value: str) -> bool:
        normalized = value.lower()
        return any(keyword in normalized for keyword in self.settings.forbidden_keywords)

    def _position_loss_guardrail_reason(self, db: Session) -> str | None:
        threshold = -abs(self.settings.hard_max_position_loss_percent)
        position = (
            db.query(BotPosition)
            .filter(BotPosition.unrealized_pnl_percent <= threshold)
            .first()
        )
        if position:
            return f"Hard position loss guardrail reached for {position.symbol}."
        return None

    def _daily_loss_guardrail_reason(self, db: Session) -> str | None:
        exposure = self.calculate_bot_exposure(db)
        if exposure <= 0:
            return None

        pnl = db.query(func.coalesce(func.sum(BotPosition.unrealized_pnl), 0)).scalar()
        daily_loss_percent = (float(pnl or 0) / exposure) * 100
        threshold = -abs(self.settings.hard_daily_loss_limit_percent)
        if daily_loss_percent <= threshold:
            return "Hard daily loss limit is reached."
        return None

    @staticmethod
    def _estimate_quantity(amount: float, price: float) -> float:
        if price <= 0:
            return 0
        return amount / price

    @staticmethod
    def _read(source: Any, key: str, default: Any = None) -> Any:
        if isinstance(source, dict):
            return source.get(key, default)
        return getattr(source, key, default)

    @staticmethod
    def _reject(reason: str) -> dict[str, bool | str]:
        return {"approved": False, "reason": reason}
