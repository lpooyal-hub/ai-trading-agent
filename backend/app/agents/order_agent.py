from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.models import AgentDecision, DecisionStatus, TradeOrder
from app.services.trading_service import TradingService


@dataclass
class OrderAgentResult:
    attempted: bool
    order: TradeOrder | None
    reason: str


class OrderAgent:
    """Execute approved paper orders when automation policy allows it."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.trading_service = TradingService(self.settings)

    def run_paper_auto(self, db: Session, decision: AgentDecision) -> OrderAgentResult:
        allowed, reason = self._paper_auto_decision_allowed(decision)
        if not allowed:
            return OrderAgentResult(attempted=False, order=None, reason=reason)

        order = self.trading_service.execute_approved_decision(db, decision)
        return OrderAgentResult(attempted=True, order=order, reason="Paper auto order execution attempted.")

    def _paper_auto_decision_allowed(self, decision: AgentDecision) -> tuple[bool, str]:
        if not self.settings.paper_auto_enabled:
            return False, "PAPER_AUTO_ENABLED is false."
        if decision.status != DecisionStatus.PENDING:
            return False, "Decision is not pending."
        if decision.confidence < self.settings.agent_auto_execute_min_confidence:
            return False, "Decision confidence is below paper auto threshold."
        if decision.recommended_order_amount > self.settings.agent_auto_execute_max_order_amount_usd:
            return False, "Decision order amount exceeds paper auto limit."
        return True, "Paper auto policy allows execution."
