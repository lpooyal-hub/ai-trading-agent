from typing import Protocol

from sqlalchemy.orm import Session

from app.config import Settings
from app.models import AgentAction, AgentDecision, OrderSide, OrderStatus, TradeOrder


class ExecutionAdapter(Protocol):
    mode: str

    def execute(
        self,
        db: Session,
        decision: AgentDecision,
        commit: bool = True,
    ) -> TradeOrder:
        ...

    def preview_warnings(self) -> list[str]:
        ...


class PaperExecutionAdapter:
    mode = "DRY_RUN_SIMULATION"

    def __init__(self, simulation_service):
        self.simulation_service = simulation_service

    def execute(
        self,
        db: Session,
        decision: AgentDecision,
        commit: bool = True,
    ) -> TradeOrder:
        if decision.action == AgentAction.BUY:
            return self.simulation_service.simulate_buy_order(db, decision, commit=commit)
        return self.simulation_service.simulate_sell_order(db, decision, commit=commit)

    def preview_warnings(self) -> list[str]:
        return []


class BlockedLiveExecutionAdapter:
    mode = "LIVE_ORDER_BLOCKED"

    def __init__(self, settings: Settings):
        self.settings = settings

    def execute(
        self,
        db: Session,
        decision: AgentDecision,
        commit: bool = True,
    ) -> TradeOrder:
        order_intent = self._order_intent(decision)
        order = TradeOrder(
            decision_id=decision.id,
            symbol=decision.symbol,
            side=OrderSide.BUY if decision.action == AgentAction.BUY else OrderSide.SELL,
            quantity=0,
            price=decision.current_price,
            order_amount=decision.recommended_order_amount,
            status=OrderStatus.TODO_LIVE_ORDER_NOT_IMPLEMENTED,
            dry_run=False,
            reason="Live order execution is blocked by the explicit blocked-live adapter.",
            raw_response_json={
                "source": "blocked_live_execution_adapter",
                "order_intent": order_intent,
                "live_order_blocked": True,
                "live_order_implementation": OrderStatus.TODO_LIVE_ORDER_NOT_IMPLEMENTED.value,
                "block_reason": "No broker order endpoint is called from this public build.",
                "blockers": [
                    "BlockedLiveExecutionAdapter is active.",
                    "No real order was sent.",
                ],
            },
        )
        if commit:
            db.add(order)
            db.commit()
            db.refresh(order)
        return order

    def preview_warnings(self) -> list[str]:
        return [
            "Live order execution is blocked by BlockedLiveExecutionAdapter.",
            "No broker order endpoint will be called from this public build.",
        ]

    def _order_intent(self, decision: AgentDecision) -> dict:
        return {
            "symbol": decision.symbol,
            "side": OrderSide.BUY.value if decision.action == AgentAction.BUY else OrderSide.SELL.value,
            "quantity": self._quantity_from_decision(decision),
            "price": decision.current_price,
            "order_amount": decision.recommended_order_amount,
            "order_sizing_mode": self.settings.order_sizing_mode_normalized,
            "fractional_trading_enabled": self.settings.fractional_trading_enabled,
            "decision_id": decision.id,
            "idempotency_key": f"decision-{decision.id}-{decision.symbol}-{decision.action.value}",
        }

    def _quantity_from_decision(self, decision: AgentDecision) -> float:
        if decision.current_price <= 0:
            return 0
        quantity = decision.recommended_order_amount / decision.current_price
        if not self.settings.fractional_trading_enabled:
            return float(int(quantity))
        return round(quantity, self.settings.quantity_decimal_places_safe)
