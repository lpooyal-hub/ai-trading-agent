from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.agents.decision_agent import DecisionAgent, DecisionAgentResult
from app.models import AgentDecision, LLMPurpose, MarketSnapshot
from app.services.llm_usage_service import LLMUsageService


@dataclass
class LoggerAgentResult:
    decision: AgentDecision


class LoggerAgent:
    """Persist agent decisions and related audit records."""

    def __init__(self, decision_agent: DecisionAgent):
        self.decision_agent = decision_agent
        self.llm_usage_service = LLMUsageService()

    def save_decision_with_usage(
        self,
        db: Session,
        *,
        decision: AgentDecision,
        decision_result: DecisionAgentResult,
        market_source: str,
        candidates: list[MarketSnapshot],
        candidate_details: list[dict[str, Any]],
        news_context: dict[str, Any],
        active_universe: list[str],
        llm_mode: str,
        max_candidates_per_run: int,
        real_llm_ready: bool,
        automation_policy: dict[str, Any],
    ) -> LoggerAgentResult:
        decision.input_snapshot_json = {
            "candidate_symbols": [item.symbol for item in candidates],
            "candidate_details": candidate_details,
            "candidate_count": len(candidates),
            "max_candidates_per_run": max_candidates_per_run,
            "active_universe": active_universe,
            "market_source": market_source,
            "news_context": news_context,
            "llm_mode": llm_mode,
        }
        decision.agent_response_json = {
            **decision_result.raw_response,
            "llm_mode": llm_mode,
            "real_llm_ready": real_llm_ready,
            "response_guard_warnings": decision_result.guard_warnings,
            "automation_policy": automation_policy,
        }

        db.add(decision)
        db.flush()

        usage = decision_result.usage
        self.llm_usage_service.record_usage(
            db,
            model=decision_result.model,
            purpose=LLMPurpose.DECISION,
            symbol=decision.symbol,
            decision_id=decision.id,
            prompt_tokens=usage["prompt_tokens"],
            completion_tokens=usage["completion_tokens"],
            total_tokens=usage["total_tokens"],
            estimated_cost_usd=decision_result.estimated_cost_usd,
            latency_ms=decision_result.latency_ms,
            success=decision_result.success,
            error_message=decision_result.error_message,
            raw_usage_json={
                **usage,
                "source": decision_result.source,
                "pricing_configured": self.decision_agent.pricing_configured(),
                "raw_response": decision_result.raw_response,
            },
            commit=False,
        )

        db.commit()
        db.refresh(decision)
        return LoggerAgentResult(decision=decision)

    @staticmethod
    def save_skipped_decision(db: Session, decision: AgentDecision) -> LoggerAgentResult:
        db.add(decision)
        db.commit()
        db.refresh(decision)
        return LoggerAgentResult(decision=decision)
