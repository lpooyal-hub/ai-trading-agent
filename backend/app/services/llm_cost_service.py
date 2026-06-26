from app.config import Settings, get_settings


class LLMCostService:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    def estimate_cost_usd(self, prompt_tokens: int, completion_tokens: int) -> float:
        input_cost = (prompt_tokens / 1_000_000) * self.settings.llm_input_cost_per_1m_tokens_usd
        output_cost = (completion_tokens / 1_000_000) * self.settings.llm_output_cost_per_1m_tokens_usd
        return round(input_cost + output_cost, 8)

    def pricing_configured(self) -> bool:
        return bool(
            self.settings.llm_input_cost_per_1m_tokens_usd > 0
            or self.settings.llm_output_cost_per_1m_tokens_usd > 0
        )
