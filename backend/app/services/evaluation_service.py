from datetime import datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import (
    AgentAction,
    AgentDecision,
    DecisionEvaluation,
    EvaluationWindow,
    MarketSnapshot,
)

# Decisions the pre-filter skipped ("no candidate passed") are persisted with a
# sentinel symbol and a zero price -- there is no position and no price thesis to
# score in hindsight, so they are excluded from the evaluation backlog entirely.
_NON_EVALUABLE_SYMBOLS = {"", "NONE"}


class EvaluationService:
    @staticmethod
    def _is_evaluable(decision: AgentDecision) -> bool:
        return (
            (decision.symbol or "").strip().upper() not in _NON_EVALUABLE_SYMBOLS
            and decision.current_price > 0
        )

    @staticmethod
    def _evaluable_decision_filters() -> list:
        """SQL predicates matching `_is_evaluable`, for backlog/coverage queries."""
        return [
            func.upper(func.trim(AgentDecision.symbol)).notin_(_NON_EVALUABLE_SYMBOLS),
            AgentDecision.current_price > 0,
        ]

    def evaluate_decision(
        self,
        db: Session,
        decision_id: int,
        window: EvaluationWindow,
    ) -> DecisionEvaluation:
        decision = db.get(AgentDecision, decision_id)
        if not decision:
            raise ValueError("Decision not found.")
        if not self._is_evaluable(decision):
            raise ValueError(
                "Decision has no traded symbol or price to evaluate "
                "(pre-filter skip)."
            )

        evaluation_price = self._resolve_evaluation_price(db, decision)
        return_percent = self._calculate_return_percent(
            decision.current_price,
            evaluation_price,
        )
        was_profitable = self._was_profitable(decision.action, return_percent)
        review = self.generate_agent_self_review(decision, return_percent, was_profitable)
        evaluation = DecisionEvaluation(
            decision_id=decision.id,
            evaluation_window=window,
            price_at_decision=decision.current_price,
            price_at_evaluation=evaluation_price,
            return_percent=return_percent,
            was_profitable=was_profitable,
            agent_self_review=review["agent_self_review"],
            mistake_type=review["mistake_type"],
            improvement_note=review["improvement_note"],
            evaluation_json={
                "source": "mock_market_snapshot",
                "action": decision.action.value,
                "window": window.value,
            },
        )
        db.add(evaluation)
        db.commit()
        db.refresh(evaluation)
        return evaluation

    def evaluate_all_due_decisions(
        self,
        db: Session,
        window: EvaluationWindow = EvaluationWindow.ONE_DAY,
    ) -> list[DecisionEvaluation]:
        cutoff = self._cutoff_for_window(window)
        decisions = (
            db.query(AgentDecision)
            .filter(AgentDecision.created_at <= cutoff)
            .filter(*self._evaluable_decision_filters())
            .order_by(AgentDecision.created_at.desc())
            .all()
        )
        evaluations: list[DecisionEvaluation] = []

        for decision in decisions:
            existing = (
                db.query(DecisionEvaluation)
                .filter(DecisionEvaluation.decision_id == decision.id)
                .filter(DecisionEvaluation.evaluation_window == window)
                .first()
            )
            if existing:
                continue
            evaluations.append(self.evaluate_decision(db, decision.id, window))

        return evaluations

    def get_status(self, db: Session) -> dict:
        total_decisions = (
            db.query(AgentDecision).filter(*self._evaluable_decision_filters()).count()
        )
        total_evaluations = db.query(DecisionEvaluation).count()
        latest_evaluated_at = db.query(func.max(DecisionEvaluation.evaluated_at)).scalar()
        windows = []
        for window in EvaluationWindow:
            cutoff = self._cutoff_for_window(window)
            eligible_count = (
                db.query(AgentDecision)
                .filter(AgentDecision.created_at <= cutoff)
                .filter(*self._evaluable_decision_filters())
                .count()
            )
            evaluated_count = (
                db.query(DecisionEvaluation.decision_id)
                .join(AgentDecision, DecisionEvaluation.decision_id == AgentDecision.id)
                .filter(DecisionEvaluation.evaluation_window == window)
                .filter(AgentDecision.created_at <= cutoff)
                .filter(*self._evaluable_decision_filters())
                .distinct()
                .count()
            )
            pending_count = max(eligible_count - evaluated_count, 0)
            not_due_count = max(total_decisions - eligible_count, 0)
            coverage_percent = (
                evaluated_count / eligible_count * 100
                if eligible_count
                else 0
            )
            windows.append(
                {
                    "window": window.value,
                    "eligible_count": eligible_count,
                    "evaluated_count": evaluated_count,
                    "pending_count": pending_count,
                    "not_due_count": not_due_count,
                    "coverage_percent": coverage_percent,
                }
            )
        return {
            "total_decisions": total_decisions,
            "total_evaluations": total_evaluations,
            "latest_evaluated_at": latest_evaluated_at,
            "windows": windows,
        }

    @staticmethod
    def _cutoff_for_window(window: EvaluationWindow) -> datetime:
        days_by_window = {
            EvaluationWindow.ONE_DAY: 1,
            EvaluationWindow.THREE_DAYS: 3,
            EvaluationWindow.SEVEN_DAYS: 7,
            EvaluationWindow.THIRTY_DAYS: 30,
        }
        return datetime.utcnow() - timedelta(days=days_by_window[window])

    def generate_agent_self_review(
        self,
        decision: AgentDecision,
        return_percent: float,
        was_profitable: bool,
    ) -> dict[str, str | None]:
        if was_profitable:
            return {
                "agent_self_review": (
                    f"The {decision.action.value} decision was directionally helpful "
                    f"for this mock evaluation window."
                ),
                "mistake_type": None,
                "improvement_note": "Keep comparing the thesis against later market snapshots.",
            }

        return {
            "agent_self_review": (
                f"The {decision.action.value} decision did not look favorable in hindsight "
                f"for this mock evaluation window."
            ),
            "mistake_type": "directional_error",
            "improvement_note": "Review whether volatility, confidence, or candidate filtering was too loose.",
        }

    def _resolve_evaluation_price(self, db: Session, decision: AgentDecision) -> float:
        # Read-only: use the most recent stored snapshot for this symbol, which
        # the market agent refreshes every cycle during the trading day. This
        # must never trigger a live universe refresh -- doing so once per
        # backlogged decision stampeded the Toss quote API at each session open
        # and starved the rest of the day's cycles of market data.
        latest_snapshot = (
            db.query(MarketSnapshot)
            .filter(MarketSnapshot.symbol == decision.symbol)
            .order_by(MarketSnapshot.created_at.desc())
            .first()
        )
        if latest_snapshot:
            return latest_snapshot.price

        return decision.current_price

    @staticmethod
    def _calculate_return_percent(price_at_decision: float, price_at_evaluation: float) -> float:
        if price_at_decision <= 0:
            return 0
        return ((price_at_evaluation - price_at_decision) / price_at_decision) * 100

    @staticmethod
    def _was_profitable(action: AgentAction, return_percent: float) -> bool:
        if action == AgentAction.BUY:
            return return_percent > 0
        if action == AgentAction.SELL:
            return return_percent < 0
        return abs(return_percent) < 1
