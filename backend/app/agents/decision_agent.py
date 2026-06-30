from dataclasses import dataclass
from typing import Any

from app.clients.llm_client import LLMCallResult, LLMClient
from app.clients.mock_llm_client import MockLLMClient
from app.config import Settings, get_settings
from app.services.llm_cost_service import LLMCostService
from app.strategy.decision_response_guard import DecisionResponseGuard


@dataclass
class DecisionAgentResult:
    response: dict[str, Any]
    raw_response: dict[str, Any]
    usage: dict[str, Any]
    estimated_cost_usd: float
    latency_ms: int
    success: bool
    error_message: str | None
    model: str
    source: str
    guard_warnings: list[str]

    @property
    def guard_blocked(self) -> bool:
        return bool(self.guard_warnings)


class DecisionAgent:
    """Call the configured decision LLM and normalize its response."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.llm_client = MockLLMClient() if self.settings.use_mock_data else LLMClient(self.settings)
        self.cost_service = LLMCostService(self.settings)
        self.response_guard = DecisionResponseGuard(
            max_order_amount_usd=self.settings.max_order_amount_usd,
        )

    def run(self, candidates: list[dict]) -> DecisionAgentResult:
        llm_result = self.llm_client.create_decision(candidates)
        guarded_response = self.response_guard.normalize(
            llm_result.parsed_response,
            candidates,
        )
        usage = llm_result.usage
        estimated_cost = self.cost_service.estimate_cost_usd(
            usage["prompt_tokens"],
            usage["completion_tokens"],
        )
        return self._result(
            llm_result=llm_result,
            response=guarded_response.response,
            estimated_cost_usd=estimated_cost,
            guard_warnings=guarded_response.warnings,
        )

    def pricing_configured(self) -> bool:
        return self.cost_service.pricing_configured()

    def _result(
        self,
        *,
        llm_result: LLMCallResult,
        response: dict[str, Any],
        estimated_cost_usd: float,
        guard_warnings: list[str],
    ) -> DecisionAgentResult:
        return DecisionAgentResult(
            response=response,
            raw_response=llm_result.raw_response,
            usage=llm_result.usage,
            estimated_cost_usd=estimated_cost_usd,
            latency_ms=llm_result.latency_ms,
            success=llm_result.success,
            error_message=llm_result.error_message,
            model=self.llm_client.model,
            source=self.llm_client.__class__.__name__,
            guard_warnings=guard_warnings,
        )
