from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models import DecisionEvaluation, EvaluationWindow
from app.services.evaluation_service import EvaluationService


@dataclass
class EvaluationAgentRunResult:
    evaluations: list[DecisionEvaluation]

    @property
    def created_count(self) -> int:
        return len(self.evaluations)


class EvaluationAgent:
    """Evaluate finished decisions and summarize hindsight performance."""

    def __init__(self):
        self.evaluation_service = EvaluationService()

    def evaluate_decision(
        self,
        db: Session,
        decision_id: int,
        window: EvaluationWindow,
    ) -> DecisionEvaluation:
        return self.evaluation_service.evaluate_decision(db, decision_id, window)

    def run_due_evaluations(
        self,
        db: Session,
        window: EvaluationWindow = EvaluationWindow.ONE_DAY,
    ) -> EvaluationAgentRunResult:
        return EvaluationAgentRunResult(
            evaluations=self.evaluation_service.evaluate_all_due_decisions(db, window),
        )

    def get_status(self, db: Session) -> dict:
        return self.evaluation_service.get_status(db)
