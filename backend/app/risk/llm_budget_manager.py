from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.services.llm_usage_service import LLMUsageService


class LLMBudgetManager:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.usage_service = LLMUsageService()

    def check_budget(self, db: Session) -> dict[str, bool | str | float | int]:
        summary = self.usage_service.summarize(db)

        if summary["today_estimated_cost_usd"] >= self.settings.llm_daily_cost_limit_usd:
            return self._reject(
                "daily LLM cost limit exceeded",
                summary,
            )
        if summary["monthly_estimated_cost_usd"] >= self.settings.llm_monthly_cost_limit_usd:
            return self._reject(
                "monthly LLM cost limit exceeded",
                summary,
            )
        if summary["today_total_tokens"] >= self.settings.llm_daily_token_limit:
            return self._reject(
                "daily LLM token limit exceeded",
                summary,
            )

        return {
            "approved": True,
            "reason": "LLM budget available.",
            "daily_cost_remaining_usd": max(
                self.settings.llm_daily_cost_limit_usd - summary["today_estimated_cost_usd"],
                0,
            ),
            "monthly_cost_remaining_usd": max(
                self.settings.llm_monthly_cost_limit_usd - summary["monthly_estimated_cost_usd"],
                0,
            ),
            "daily_tokens_remaining": max(
                self.settings.llm_daily_token_limit - summary["today_total_tokens"],
                0,
            ),
            **summary,
        }

    def _reject(self, reason: str, summary: dict) -> dict[str, bool | str | float | int]:
        return {
            "approved": False,
            "reason": reason,
            "daily_cost_remaining_usd": max(
                self.settings.llm_daily_cost_limit_usd - summary["today_estimated_cost_usd"],
                0,
            ),
            "monthly_cost_remaining_usd": max(
                self.settings.llm_monthly_cost_limit_usd - summary["monthly_estimated_cost_usd"],
                0,
            ),
            "daily_tokens_remaining": max(
                self.settings.llm_daily_token_limit - summary["today_total_tokens"],
                0,
            ),
            **summary,
        }
