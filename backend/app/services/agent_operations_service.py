from datetime import datetime

from sqlalchemy.orm import Session

from app.models import (
    AgentDecision,
    DecisionEvaluation,
    DecisionStatus,
    OrderStatus,
    TradeOrder,
)


class AgentOperationsService:
    def get_operations(self, db: Session) -> dict:
        last_decision = self._last_decision(db)
        last_order = self._last_order(db)
        last_evaluation = self._last_evaluation(db)
        latest_activity_at = self._latest_activity_at(
            [
                last_decision.created_at if last_decision else None,
                last_order.created_at if last_order else None,
                last_evaluation.evaluated_at if last_evaluation else None,
            ]
        )
        return {
            "last_decision_id": last_decision.id if last_decision else None,
            "last_decision_status": last_decision.status.value if last_decision else None,
            "last_decision_symbol": last_decision.symbol if last_decision else None,
            "last_order_id": last_order.id if last_order else None,
            "last_order_status": last_order.status.value if last_order else None,
            "last_order_symbol": last_order.symbol if last_order else None,
            "last_evaluation_id": last_evaluation.id if last_evaluation else None,
            "last_evaluation_window": last_evaluation.evaluation_window.value if last_evaluation else None,
            "pending_decision_count": self._decision_count(db, DecisionStatus.PENDING),
            "executable_decision_count": self._executable_decision_count(db),
            "simulated_order_count": self._order_count(db, OrderStatus.SIMULATED),
            "rejected_order_count": self._order_count(db, OrderStatus.REJECTED),
            "failed_order_count": self._order_count(db, OrderStatus.FAILED),
            "latest_activity_at": latest_activity_at,
        }

    @staticmethod
    def _last_decision(db: Session) -> AgentDecision | None:
        return db.query(AgentDecision).order_by(AgentDecision.created_at.desc()).first()

    @staticmethod
    def _last_order(db: Session) -> TradeOrder | None:
        return db.query(TradeOrder).order_by(TradeOrder.created_at.desc()).first()

    @staticmethod
    def _last_evaluation(db: Session) -> DecisionEvaluation | None:
        return db.query(DecisionEvaluation).order_by(DecisionEvaluation.evaluated_at.desc()).first()

    @staticmethod
    def _decision_count(db: Session, status: DecisionStatus) -> int:
        return db.query(AgentDecision).filter(AgentDecision.status == status).count()

    @staticmethod
    def _executable_decision_count(db: Session) -> int:
        return (
            db.query(AgentDecision)
            .filter(AgentDecision.status == DecisionStatus.PENDING)
            .filter(AgentDecision.symbol != "NONE")
            .count()
        )

    @staticmethod
    def _order_count(db: Session, status: OrderStatus) -> int:
        return db.query(TradeOrder).filter(TradeOrder.status == status).count()

    @staticmethod
    def _latest_activity_at(values: list[datetime | None]) -> datetime | None:
        timestamps = [value for value in values if value is not None]
        return max(timestamps) if timestamps else None
