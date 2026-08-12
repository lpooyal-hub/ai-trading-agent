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
        action = self._read(decision, "action", "")
        amount = float(self._read(decision, "recommended_order_amount", 0) or 0)
        price = float(self._read(decision, "current_price", 0) or 0)
        name = product_name or self._read(decision, "name", symbol)

        if not self.settings.dry_run and not self.settings.live_trading_enabled:
            return self._reject("Live trading is disabled while DRY_RUN is false.")

        if not self.settings.dry_run and self.settings.max_order_amount_limit_krw is None:
            return self._reject("MAX_ORDER_AMOUNT_KRW must be positive for live trading.")

        legacy_position = self._get_legacy_position(db, symbol)
        bot_position = self._get_bot_position(db, symbol)
        is_bot_exit = action == AgentAction.SELL and bot_position is not None

        if symbol not in self.settings.allowed_symbols and not is_bot_exit:
            return self._reject(f"Symbol {symbol} is outside the active universe.")

        if symbol in self.settings.protected_symbols and not is_bot_exit:
            return self._reject(f"Symbol {symbol} is protected and cannot be traded.")

        if self._contains_forbidden_keyword(name) and not is_bot_exit:
            return self._reject("Product name contains a forbidden leveraged/inverse keyword.")

        if legacy_position and not bot_position:
            return self._reject(f"Symbol {symbol} exists only as a protected legacy position.")

        max_order_amount = self.settings.max_order_amount_limit_krw
        if not is_bot_exit and max_order_amount is not None and amount > max_order_amount:
            return self._reject("Recommended order amount exceeds MAX_ORDER_AMOUNT_KRW.")

        if action == AgentAction.BUY and amount < self.settings.min_order_amount_krw:
            return self._reject("Recommended order amount is below MIN_ORDER_AMOUNT_KRW.")

        estimated_quantity = self._estimate_quantity(amount, price)
        if (
            action == AgentAction.BUY
            and not self.settings.fractional_trading_enabled
            and estimated_quantity < 1
        ):
            return self._reject("Fractional trading is disabled and estimated quantity is below 1 share.")

        exposure = self.calculate_bot_exposure(db)
        if action == AgentAction.BUY and amount + exposure > self.settings.bot_capital_limit_krw:
            return self._reject("Total bot invested amount would exceed BOT_CAPITAL_LIMIT_KRW.")

        budget = (
            available_bot_budget
            if available_bot_budget is not None
            else self.settings.bot_capital_limit_krw - exposure
        )
        if action == AgentAction.BUY and amount > budget:
            return self._reject("Available bot budget is insufficient.")

        symbol_exposure_reason = self._symbol_exposure_guardrail_reason(bot_position, amount, action)
        if symbol_exposure_reason:
            return self._reject(symbol_exposure_reason)

        if action == AgentAction.BUY and not bot_position:
            open_positions = self.count_open_positions(db)
            if open_positions >= self.settings.max_positions:
                return self._reject("MAX_POSITIONS would be exceeded.")

        if (
            not is_bot_exit
            and self.settings.max_daily_trades > 0
            and self.count_today_simulated_trades(db) >= self.settings.max_daily_trades
        ):
            return self._reject("MAX_DAILY_TRADES has been reached.")

        if action == AgentAction.SELL:
            owned_quantity = bot_position.quantity if bot_position else 0
            requested_quantity = sell_quantity or estimated_quantity
            if requested_quantity > owned_quantity:
                return self._reject("Sell quantity exceeds bot-owned quantity.")

        if action == AgentAction.BUY:
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

    def _symbol_exposure_guardrail_reason(
        self,
        bot_position: BotPosition | None,
        order_amount: float,
        action: AgentAction,
    ) -> str | None:
        if action != AgentAction.BUY:
            return None

        max_percent = max(self.settings.max_symbol_exposure_percent, 0)
        if max_percent <= 0:
            return None

        max_symbol_exposure = self.settings.bot_capital_limit_krw * (max_percent / 100)
        current_symbol_exposure = bot_position.total_invested_amount if bot_position else 0
        projected_symbol_exposure = current_symbol_exposure + order_amount
        if projected_symbol_exposure > max_symbol_exposure:
            return (
                "Symbol exposure limit would be exceeded "
                f"({projected_symbol_exposure:.2f} > {max_symbol_exposure:.2f})."
            )
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
