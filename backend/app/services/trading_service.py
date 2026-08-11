from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.clients.toss_client import TossClient
from app.execution.adapters import (
    BlockedLiveExecutionAdapter,
    ExecutionAdapter,
    PaperExecutionAdapter,
    TossLiveExecutionAdapter,
)
from app.agents.risk_agent import RiskAgent
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


class TradingService:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.risk_agent = RiskAgent(self.settings)

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
        result = self.risk_agent.validate_decision(
            decision,
            db,
            available_bot_budget=available_budget,
            sell_quantity=estimated_quantity if decision.action == AgentAction.SELL else None,
        )
        return {
            "decision_id": decision.id,
            "approved": result.approved,
            "reason": result.reason,
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

        risk_result = self.risk_agent.validate_decision(
            decision,
            db,
            available_bot_budget=self.calculate_available_budget(db),
        )
        if not risk_result.approved:
            decision.status = DecisionStatus.REJECTED
            decision.rejection_reason = risk_result.reason
            order = self._reject_order(db, decision, risk_result.reason, commit=False)
            db.add(order)
            db.commit()
            db.refresh(order)
            return order

        decision.status = DecisionStatus.APPROVED
        order = self._execution_adapter().execute(db, decision, commit=False)

        db.add(order)
        db.flush()
        decision.executed_order_id = order.id
        decision.status = (
            DecisionStatus.EXECUTED
            if order.status in {OrderStatus.SIMULATED, OrderStatus.LIVE_SUBMITTED}
            else DecisionStatus.REJECTED
        )
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
        position = self._get_bot_position(db, decision.symbol)
        quantity_before = position.quantity if position else 0
        quantity_after = quantity_before + quantity
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
                "order_sizing_mode": self.settings.order_sizing_mode_normalized,
                "fractional_trading_enabled": self.settings.fractional_trading_enabled,
                "simulated_fill": {
                    "side": OrderSide.BUY.value,
                    "quantity": quantity,
                    "price": decision.current_price,
                    "order_amount": decision.recommended_order_amount,
                    "position_quantity_before": quantity_before,
                    "position_quantity_after": quantity_after,
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
        quantity_before = position.quantity if position else 0
        quantity = min(self._quantity_from_decision(decision), position.quantity if position else 0)
        order_amount = quantity * decision.current_price
        remaining_quantity = max(quantity_before - quantity, 0)
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
                "order_sizing_mode": self.settings.order_sizing_mode_normalized,
                "fractional_trading_enabled": self.settings.fractional_trading_enabled,
                "simulated_fill": {
                    "side": OrderSide.SELL.value,
                    "quantity": quantity,
                    "price": decision.current_price,
                    "order_amount": order_amount,
                    "position_quantity_before": quantity_before,
                    "position_quantity_after": remaining_quantity,
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
            self._refresh_position_pnl(position)
        db.commit()
        return positions

    def sync_live_order_status(self, db: Session, order: TradeOrder) -> TradeOrder:
        if order.dry_run or order.status not in {
            OrderStatus.LIVE_SUBMITTED,
            OrderStatus.LIVE_PARTIAL,
        }:
            return order

        broker_order_id = self._broker_order_id(order)
        if not broker_order_id:
            order.raw_response_json = self._merged_raw_response(
                order,
                {
                    "broker_status_sync": {
                        "success": False,
                        "message": "Broker order id is missing from live order response.",
                        "position_applied": self._live_position_applied(order),
                    }
                },
            )
            db.commit()
            db.refresh(order)
            return order

        response = TossClient(self.settings).get_live_order_status(order_id=broker_order_id)
        if not response.get("success"):
            order.raw_response_json = self._merged_raw_response(
                order,
                {
                    "broker_status_sync": {
                        "success": False,
                        "broker_order_id": broker_order_id,
                        "broker_response": response,
                        "position_applied": self._live_position_applied(order),
                    }
                },
            )
            db.commit()
            db.refresh(order)
            return order

        status_payload = response.get("data") if isinstance(response.get("data"), dict) else response
        status_update = self._live_status_update(status_payload)
        order.status = status_update["status"]
        filled_quantity = status_update["filled_quantity"] or order.quantity
        fill_price = status_update["fill_price"] or order.price
        fill_amount = status_update["fill_amount"] or filled_quantity * fill_price

        position_applied = self._live_position_applied(order)
        if order.status == OrderStatus.LIVE_FILLED and not position_applied:
            self._apply_live_fill(db, order, filled_quantity, fill_price, fill_amount)
            position_applied = True

        order.raw_response_json = self._merged_raw_response(
            order,
            {
                "broker_status_sync": {
                    "success": True,
                    "broker_order_id": broker_order_id,
                    "normalized_status": order.status.value,
                    "filled_quantity": filled_quantity,
                    "fill_price": fill_price,
                    "fill_amount": fill_amount,
                    "position_applied": position_applied,
                    "broker_response": response,
                }
            },
        )
        order.reason = self._live_status_reason(order.status)
        db.commit()
        db.refresh(order)
        return order

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

    def _apply_live_fill(
        self,
        db: Session,
        order: TradeOrder,
        quantity: float,
        fill_price: float,
        fill_amount: float,
    ) -> None:
        if quantity <= 0:
            return
        if order.side == OrderSide.BUY:
            self._apply_live_buy_fill(db, order, quantity, fill_price, fill_amount)
            return
        self._apply_sell_position(self._get_bot_position(db, order.symbol), quantity, fill_amount)

    def _apply_live_buy_fill(
        self,
        db: Session,
        order: TradeOrder,
        quantity: float,
        fill_price: float,
        fill_amount: float,
    ) -> None:
        position = self._get_bot_position(db, order.symbol)
        sector = order.decision.sector if order.decision else "unknown"
        if not position:
            position = BotPosition(
                symbol=order.symbol,
                name=order.symbol,
                sector=sector,
                quantity=quantity,
                avg_buy_price=fill_price,
                total_invested_amount=fill_amount,
                current_price=fill_price,
                unrealized_pnl=0,
                unrealized_pnl_percent=0,
                status="OPEN",
            )
            self._refresh_position_pnl(position)
            db.add(position)
            return

        new_total = position.total_invested_amount + fill_amount
        new_quantity = position.quantity + quantity
        position.quantity = new_quantity
        position.avg_buy_price = new_total / new_quantity if new_quantity else 0
        position.total_invested_amount = new_total
        position.current_price = fill_price
        position.status = "OPEN"
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

    def _apply_sell_position(
        self,
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
        self._refresh_position_pnl(position)

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

    def _execution_mode(self) -> str:
        if self.settings.dry_run or self.settings.live_trading_enabled:
            return self._execution_adapter().mode
        return "BLOCKED_LIVE_DISABLED"

    def _execution_adapter(self) -> ExecutionAdapter:
        if not self.settings.dry_run and self.settings.live_trading_enabled:
            if self.settings.toss_live_order_ready and self.settings.admin_auth_enabled:
                return TossLiveExecutionAdapter(self.settings)
            return BlockedLiveExecutionAdapter(self.settings)
        return PaperExecutionAdapter(self)

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
        if execution_mode == "LIVE_ORDER":
            warnings.extend(TossLiveExecutionAdapter(self.settings).preview_warnings())
        if execution_mode == "LIVE_ORDER_BLOCKED":
            warnings.extend(BlockedLiveExecutionAdapter(self.settings).preview_warnings())
        if execution_mode == "BLOCKED_LIVE_DISABLED":
            warnings.append("Live order execution is blocked because LIVE_TRADING_ENABLED is false.")
        if legacy_protected:
            warnings.append("The symbol exists as a protected legacy position.")
        if decision.action == AgentAction.HOLD:
            warnings.append("HOLD decisions are not executable.")
        if decision.recommended_order_amount <= 0:
            warnings.append("Recommended order amount is zero.")
        return warnings

    def _quantity_from_decision(self, decision: AgentDecision) -> float:
        if decision.current_price <= 0:
            return 0
        quantity = decision.recommended_order_amount / decision.current_price
        if not self.settings.fractional_trading_enabled:
            return float(int(quantity))
        return round(quantity, self.settings.quantity_decimal_places_safe)

    @staticmethod
    def _broker_order_id(order: TradeOrder) -> str | None:
        raw = order.raw_response_json or {}
        values = [
            raw.get("broker_order_id"),
            raw.get("order_id"),
        ]
        broker_response = raw.get("broker_response")
        if isinstance(broker_response, dict):
            values.extend(TradingService._find_first_value(broker_response, key) for key in [
                "order_id",
                "orderId",
                "order_no",
                "orderNo",
                "ord_no",
                "ordNo",
                "id",
            ])
        order_intent = raw.get("order_intent")
        if isinstance(order_intent, dict):
            values.append(order_intent.get("idempotency_key"))
        for value in values:
            if value:
                return str(value)
        return None

    @staticmethod
    def _live_status_update(payload: dict) -> dict:
        status_value = str(
            TradingService._find_first_value(payload, "status")
            or TradingService._find_first_value(payload, "order_status")
            or TradingService._find_first_value(payload, "orderStatus")
            or TradingService._find_first_value(payload, "state")
            or ""
        ).upper()
        filled_quantity = TradingService._float_value(
            TradingService._find_first_value(payload, "filled_quantity")
            or TradingService._find_first_value(payload, "filledQuantity")
            or TradingService._find_first_value(payload, "executed_quantity")
            or TradingService._find_first_value(payload, "executedQuantity")
            or TradingService._find_first_value(payload, "filled_qty")
        )
        fill_price = TradingService._float_value(
            TradingService._find_first_value(payload, "average_fill_price")
            or TradingService._find_first_value(payload, "averageFillPrice")
            or TradingService._find_first_value(payload, "avg_price")
            or TradingService._find_first_value(payload, "avgPrice")
            or TradingService._find_first_value(payload, "price")
        )
        fill_amount = TradingService._float_value(
            TradingService._find_first_value(payload, "filled_amount")
            or TradingService._find_first_value(payload, "filledAmount")
            or TradingService._find_first_value(payload, "executed_amount")
            or TradingService._find_first_value(payload, "executedAmount")
        )
        if any(token in status_value for token in ["PARTIAL", "PARTIALLY", "PART", "부분"]):
            normalized = OrderStatus.LIVE_PARTIAL
        elif any(token in status_value for token in ["FILLED", "EXECUTED", "COMPLETE", "DONE", "체결"]):
            normalized = OrderStatus.LIVE_FILLED
        elif any(token in status_value for token in ["CANCEL", "CANCELED", "CANCELLED", "취소"]):
            normalized = OrderStatus.LIVE_CANCELED
        elif any(token in status_value for token in ["REJECT", "FAIL", "ERROR", "거절", "실패"]):
            normalized = OrderStatus.FAILED
        else:
            normalized = OrderStatus.LIVE_SUBMITTED
        return {
            "status": normalized,
            "filled_quantity": filled_quantity,
            "fill_price": fill_price,
            "fill_amount": fill_amount,
        }

    @staticmethod
    def _find_first_value(payload: dict | list | None, key: str):
        if isinstance(payload, dict):
            if key in payload:
                return payload[key]
            for value in payload.values():
                found = TradingService._find_first_value(value, key)
                if found is not None:
                    return found
        if isinstance(payload, list):
            for item in payload:
                found = TradingService._find_first_value(item, key)
                if found is not None:
                    return found
        return None

    @staticmethod
    def _float_value(value) -> float:
        if value is None or value == "":
            return 0
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _live_position_applied(order: TradeOrder) -> bool:
        raw = order.raw_response_json or {}
        sync = raw.get("broker_status_sync")
        return bool(isinstance(sync, dict) and sync.get("position_applied"))

    @staticmethod
    def _merged_raw_response(order: TradeOrder, patch: dict) -> dict:
        raw = dict(order.raw_response_json or {})
        raw.update(patch)
        return raw

    @staticmethod
    def _live_status_reason(status: OrderStatus) -> str:
        if status == OrderStatus.LIVE_FILLED:
            return "Live order filled and broker status synchronized."
        if status == OrderStatus.LIVE_PARTIAL:
            return "Live order partially filled according to broker status."
        if status == OrderStatus.LIVE_CANCELED:
            return "Live order canceled according to broker status."
        if status == OrderStatus.FAILED:
            return "Live order failed according to broker status."
        return "Live order status synchronized."
