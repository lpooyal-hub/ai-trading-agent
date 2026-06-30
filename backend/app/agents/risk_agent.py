from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.risk.risk_manager import RiskManager


@dataclass
class RiskAgentResult:
    approved: bool
    reason: str


class RiskAgent:
    """Evaluate deterministic portfolio, budget, and guardrail risk rules."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.risk_manager = RiskManager(self.settings)

    def validate_decision(
        self,
        decision: Any,
        db: Session,
        available_bot_budget: float | None = None,
        product_name: str | None = None,
        sell_quantity: float | None = None,
    ) -> RiskAgentResult:
        result = self.risk_manager.validate_decision(
            decision,
            db,
            available_bot_budget=available_bot_budget,
            product_name=product_name,
            sell_quantity=sell_quantity,
        )
        return RiskAgentResult(
            approved=bool(result["approved"]),
            reason=str(result["reason"]),
        )
