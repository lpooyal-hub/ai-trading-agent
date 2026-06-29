from sqlalchemy.orm import Session

from app.models import AgentDecision, DecisionEvaluation, TradeJournalEntry, TradeOrder
from app.schemas import TradeJournalEntryCreate


class JournalService:
    def list_entries(self, db: Session, limit: int = 50) -> list[TradeJournalEntry]:
        return (
            db.query(TradeJournalEntry)
            .order_by(TradeJournalEntry.created_at.desc())
            .limit(limit)
            .all()
        )

    def get_entry(self, db: Session, entry_id: int) -> TradeJournalEntry | None:
        return db.get(TradeJournalEntry, entry_id)

    def get_by_decision(self, db: Session, decision_id: int) -> list[TradeJournalEntry]:
        return (
            db.query(TradeJournalEntry)
            .filter(TradeJournalEntry.decision_id == decision_id)
            .order_by(TradeJournalEntry.created_at.desc())
            .all()
        )

    def create_entry(self, db: Session, payload: TradeJournalEntryCreate) -> TradeJournalEntry | None:
        decision = db.get(AgentDecision, payload.decision_id)
        if not decision:
            return None

        order = db.get(TradeOrder, payload.order_id) if payload.order_id else None
        evaluation = db.get(DecisionEvaluation, payload.evaluation_id) if payload.evaluation_id else None
        if payload.order_id and (not order or order.decision_id != decision.id):
            return None
        if payload.evaluation_id and (not evaluation or evaluation.decision_id != decision.id):
            return None
        reward_score = payload.reward_score
        outcome_label = payload.outcome_label
        if evaluation and payload.reward_score == 0:
            reward_score = self._reward_from_evaluation(evaluation)
        if evaluation and payload.outcome_label == "PENDING_REVIEW":
            outcome_label = "PROFITABLE" if evaluation.was_profitable else "UNPROFITABLE"

        entry = TradeJournalEntry(
            decision_id=decision.id,
            order_id=order.id if order else None,
            evaluation_id=evaluation.id if evaluation else None,
            symbol=decision.symbol,
            action=decision.action,
            outcome_label=outcome_label,
            reward_score=reward_score,
            thesis_snapshot=decision.thesis,
            agent_self_feedback=payload.agent_self_feedback or self._default_feedback(decision, evaluation),
            lesson=payload.lesson,
            strategy_tags_json=payload.strategy_tags,
            journal_json={
                **payload.journal_json,
                "decision_status": decision.status.value,
                "order_status": order.status.value if order else None,
                "evaluation_window": evaluation.evaluation_window.value if evaluation else None,
            },
        )
        db.add(entry)
        db.commit()
        db.refresh(entry)
        return entry

    @staticmethod
    def _reward_from_evaluation(evaluation: DecisionEvaluation) -> float:
        reward = evaluation.return_percent / 100
        if not evaluation.was_profitable:
            reward -= 0.01
        return round(reward, 6)

    @staticmethod
    def _default_feedback(decision: AgentDecision, evaluation: DecisionEvaluation | None) -> str:
        if not evaluation:
            return "Journal entry created before outcome evaluation. Review after a fresh evaluation window is due."
        return (
            f"{decision.action.value} decision returned {evaluation.return_percent:.2f}% "
            f"over {evaluation.evaluation_window.value}. {evaluation.agent_self_review}"
        )
