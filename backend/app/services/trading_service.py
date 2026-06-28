from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.models import (
    AgentAction,
    AgentDecision,
    BotPosition,
    DecisionStatus,
    LegacyPosition,
    OrderSide,
    OrderStatus,
    TradeOrder,
)
from app.risk.risk_manager import RiskManager


class TradingService:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.risk_manager = RiskManager(self.settings)

    def preview_decision(self, db: Session, decision: AgentDecision) -> dict:
        available_budget = self.calculate_available_budget(db)
        bot_position = self._get_bot_position(db, decision.symbol)
        legacy_position = (
            db.query(LegacyPosition)
            .filter(LegacyPosition.symbol == decision.symbol)
            .filter(LegacyPosition.is_protected.is_(True))
            .first()
        )
        estimated_quantity = self._quantity_from_decision(decision)
        if decision.action == AgentAction.SELL and bot_position:
            estimated_quantity = min(estimated_quantity, bot_position.quantity)
        estimated_order_amount = (
            estimated_quantity * decision.current_price
            if decision.action == AgentAction.SELL
            else decision.recommended_order_amount
        )
        execution_mode = self._execution_mode()
        result = self.risk_manager.validate_decision(
            decision,
            db,
            available_bot_budget=available_budget,
            sell_quantity=estimated_quantity if decision.action == AgentAction.SELL else None,
        )
        return {
            "decision_id": decision.id,
            "approved": result["approved"],
            "reason": result["reason"],
            "symbol": decision.symbol,
            "action": decision.action,
            "side": self._side_for_decision(decision),
            "estimated_quantity": estimated_quantity,
            "estimated_price": decision.current_price,
            "estimated_order_amount": estimated_order_amount,
            "available_budget": available_budget,
            "bot_exposure": self.calculate_bot_exposure(db),
            "bot_owned_quantity": bot_position.quantity if bot_position else 0,
            "legacy_protected": bool(legacy_position),
            "execution_mode": execution_mode,
            "dry_run": self.settings.dry_run,
            "live_trading_enabled": self.settings.live_trading_enabled,
            "warnings": self._preview_warnings(decision, execution_mode, bool(legacy_position)),
        }

    def execute_approved_decision(self, db: Session, decision: AgentDecision) -> TradeOrder:
        if decision.status not in {DecisionStatus.PENDING, DecisionStatus.APPROVED}:
            return self._reject_order(db, decision, "Decision is not pending approval.")

        if decision.action == AgentAction.HOLD:
            decision.status = DecisionStatus.SKIPPED
            decision.rejection_reason = "HOLD decisions are not executable."
            db.commit()
            return self._reject_order(db, decision, "HOLD decisions are not executable.")

        risk_result = self.risk_manager.validate_decision(
            decision,
            db,
            available_bot_budget=self.calculate_available_budget(db),
        )
        if not risk_result["approved"]:
            decision.status = DecisionStatus.REJECTED
            decision.rejection_reason = str(risk_result["reason"])
            order = self._reject_order(db, decision, str(risk_result["reason"]), commit=False)
            db.add(order)
            db.commit()
            db.refresh(order)
            return order

        decision.status = DecisionStatus.APPROVED
        if not self.settings.dry_run and self.settings.live_trading_enabled:
            order = self._todo_live_order(db, decision, commit=False)
        elif decision.action == AgentAction.BUY:
            order = self.simulate_buy_order(db, decision, commit=False)
        else:
            order = self.simulate_sell_order(db, decision, commit=False)

        db.add(order)
        db.flush()
        decision.executed_order_id = order.id
        decision.status = DecisionStatus.EXECUTED if order.status == OrderStatus.SIMULATED else DecisionStatus.REJECTED
        db.commit()
        db.refresh(order)
        db.refresh(decision)
        return order

    def simulate_buy_order(
        self,
        db: Session,
        decision: AgentDecision,
        commit: bool = True,
    ) -> TradeOrder:
        quantity = self._quantity_from_decision(decision)
        order = TradeOrder(
            decision_id=decision.id,
            symbol=decision.symbol,
            side=OrderSide.BUY,
            quantity=quantity,
            price=decision.current_price,
            order_amount=decision.recommended_order_amount,
            status=OrderStatus.SIMULATED,
            dry_run=True,
            reason="DRY_RUN simulated buy order.",
            raw_response_json={
                "source": "trading_service",
                "dry_run": True,
                "simulated_fill": {
                    "side": OrderSide.BUY.value,
                    "quantity": quantity,
                    "price": decision.current_price,
                    "order_amount": decision.recommended_order_amount,
                },
            },
        )
        self._apply_buy_position(db, decision, quantity)
        if commit:
            db.add(order)
            db.commit()
            db.refresh(order)
        return order

    def simulate_sell_order(
        self,
        db: Session,
        decision: AgentDecision,
        commit: bool = True,
    ) -> TradeOrder:
        position = self._get_bot_position(db, decision.symbol)
        quantity = min(self._quantity_from_decision(decision), position.quantity if position else 0)
        order_amount = quantity * decision.current_price
        order = TradeOrder(
            decision_id=decision.id,
            symbol=decision.symbol,
            side=OrderSide.SELL,
            quantity=quantity,
            price=decision.current_price,
            order_amount=order_amount,
            status=OrderStatus.SIMULATED,
            dry_run=True,
            reason="DRY_RUN simulated sell order.",
            raw_response_json={
                "source": "trading_service",
                "dry_run": True,
                "simulated_fill": {
                    "side": OrderSide.SELL.value,
                    "quantity": quantity,
                    "price": decision.current_price,
                    "order_amount": order_amount,
                },
            },
        )
        self._apply_sell_position(position, quantity, order_amount)
        if commit:
            db.add(order)
            db.commit()
            db.refresh(order)
        return order

    def calculate_available_budget(self, db: Session) -> float:
        return max(
            self.settings.bot_capital_limit_usd
            - self.calculate_bot_exposure(db)
            - self.settings.min_cash_reserve_usd,
            0,
        )

    def calculate_bot_exposure(self, db: Session) -> float:
        positions = db.query(BotPosition).filter(BotPosition.status == "OPEN").all()
        return sum(position.total_invested_amount for position in positions)

    def sync_bot_positions(self, db: Session) -> list[BotPosition]:
        positions = db.query(BotPosition).all()
        for position in positions:
            position.unrealized_pnl = (
                position.current_price - position.avg_buy_price
            ) * position.quantity
            invested = position.total_invested_amount
            position.unrealized_pnl_percent = (
                position.unrealized_pnl / invested * 100
                if invested
                else 0
            )
        db.commit()
        return positions

    def _apply_buy_position(
        self,
        db: Session,
        decision: AgentDecision,
        quantity: float,
    ) -> None:
        position = self._get_bot_position(db, decision.symbol)
        if not position:
            position = BotPosition(
                symbol=decision.symbol,
                name=decision.symbol,
                sector=decision.sector,
                quantity=quantity,
                avg_buy_price=decision.current_price,
                total_invested_amount=decision.recommended_order_amount,
                current_price=decision.current_price,
                unrealized_pnl=0,
                unrealized_pnl_percent=0,
                status="OPEN",
            )
            self._refresh_position_pnl(position)
            db.add(position)
            return

        new_total = position.total_invested_amount + decision.recommended_order_amount
        new_quantity = position.quantity + quantity
        position.quantity = new_quantity
        position.avg_buy_price = new_total / new_quantity if new_quantity else 0
        position.total_invested_amount = new_total
        position.current_price = decision.current_price
        self._refresh_position_pnl(position)

    @staticmethod
    def _refresh_position_pnl(position: BotPosition) -> None:
        position.unrealized_pnl = (
            position.current_price - position.avg_buy_price
        ) * position.quantity
        invested = position.total_invested_amount
        position.unrealized_pnl_percent = (
            position.unrealized_pnl / invested * 100
            if invested
            else 0
        )

    @staticmethod
    def _apply_sell_position(
        position: BotPosition | None,
        quantity: float,
        order_amount: float,
    ) -> None:
        if not position or quantity <= 0:
            return

        remaining_quantity = max(position.quantity - quantity, 0)
        sold_cost_basis = min(position.total_invested_amount, position.avg_buy_price * quantity)
        position.quantity = remaining_quantity
        position.total_invested_amount = max(position.total_invested_amount - sold_cost_basis, 0)
        position.current_price = order_amount / quantity if quantity else position.current_price
        position.status = "CLOSED" if remaining_quantity == 0 else "OPEN"

    def _get_bot_position(self, db: Session, symbol: str) -> BotPosition | None:
        return (
            db.query(BotPosition)
            .filter(BotPosition.symbol == symbol)
            .filter(BotPosition.status == "OPEN")
            .first()
        )

    def _reject_order(
        self,
        db: Session,
        decision: AgentDecision,
        reason: str,
        commit: bool = True,
    ) -> TradeOrder:
        order = TradeOrder(
            decision_id=decision.id,
            symbol=decision.symbol,
            side=OrderSide.BUY if decision.action != AgentAction.SELL else OrderSide.SELL,
            quantity=0,
            price=decision.current_price,
            order_amount=0,
            status=OrderStatus.REJECTED,
            dry_run=self.settings.dry_run,
            reason=reason,
            raw_response_json={"source": "trading_service"},
        )
        if commit:
            db.add(order)
            db.commit()
            db.refresh(order)
        return order

    def _todo_live_order(
        self,
        db: Session,
        decision: AgentDecision,
        commit: bool = True,
    ) -> TradeOrder:
        order = TradeOrder(
            decision_id=decision.id,
            symbol=decision.symbol,
            side=OrderSide.BUY if decision.action == AgentAction.BUY else OrderSide.SELL,
            quantity=0,
            price=decision.current_price,
            order_amount=decision.recommended_order_amount,
            status=OrderStatus.TODO_LIVE_ORDER_NOT_IMPLEMENTED,
            dry_run=False,
            reason="Live order execution is not connected yet.",
            raw_response_json={"source": "trading_service"},
        )
        if commit:
            db.add(order)
            db.commit()
            db.refresh(order)
        return order

    def _execution_mode(self) -> str:
        if self.settings.dry_run:
            return "DRY_RUN_SIMULATION"
        if self.settings.live_trading_enabled:
            return "LIVE_TODO_NOT_IMPLEMENTED"
        return "BLOCKED_LIVE_DISABLED"

    @staticmethod
    def _side_for_decision(decision: AgentDecision) -> OrderSide | None:
        if decision.action == AgentAction.BUY:
            return OrderSide.BUY
        if decision.action == AgentAction.SELL:
            return OrderSide.SELL
        return None

    def _preview_warnings(
        self,
        decision: AgentDecision,
        execution_mode: str,
        legacy_protected: bool,
    ) -> list[str]:
        warnings: list[str] = []
        if execution_mode != "DRY_RUN_SIMULATION":
            warnings.append("This decision will not create a DRY_RUN simulated order.")
        if legacy_protected:
            warnings.append("The symbol exists as a protected legacy position.")
        if decision.action == AgentAction.HOLD:
            warnings.append("HOLD decisions are not executable.")
        if decision.recommended_order_amount <= 0:
            warnings.append("Recommended order amount is zero.")
        return warnings

    @staticmethod
    def _quantity_from_decision(decision: AgentDecision) -> float:
        if decision.current_price <= 0:
            return 0
        return decision.recommended_order_amount / decision.current_price
