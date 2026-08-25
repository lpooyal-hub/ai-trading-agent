from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.services.llm_usage_service import LLMUsageService


class LLMBudgetManager:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.usage_service = LLMUsageService()

    def check_budget(self, db: Session, *, include_cooldown: bool = True) -> dict[str, Any]:
        summary = self.usage_service.summarize(db)
        cooldown_usage = self.usage_service.latest_usage_for_cooldown(db)
        cooldown_at = cooldown_usage.created_at if cooldown_usage else None

        if summary["today_estimated_cost_usd"] >= self.settings.llm_daily_cost_limit_usd:
            return self._reject(
                "daily LLM cost limit exceeded",
                summary,
                cooldown_at,
            )
        if summary["monthly_estimated_cost_usd"] >= self.settings.llm_monthly_cost_limit_usd:
            return self._reject(
                "monthly LLM cost limit exceeded",
                summary,
                cooldown_at,
            )
        if summary["today_total_tokens"] >= self.settings.llm_daily_token_limit:
            return self._reject(
                "daily LLM token limit exceeded",
                summary,
                cooldown_at,
            )
        if summary["today_calls"] >= self.settings.llm_daily_call_limit:
            return self._reject(
                "daily LLM call limit exceeded",
                summary,
                cooldown_at,
            )

        cooldown = self._cooldown_remaining_minutes(cooldown_at)
        if include_cooldown and cooldown > 0:
            return self._reject(
                f"LLM cooldown active for {cooldown} more minute(s)",
                summary,
                cooldown_at,
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
            "daily_calls_remaining": max(
                self.settings.llm_daily_call_limit - summary["today_calls"],
                0,
            ),
            "cooldown_remaining_minutes": 0,
            **summary,
        }

    def _reject(self, reason: str, summary: dict, cooldown_at: datetime | None) -> dict[str, Any]:
        cooldown = self._cooldown_remaining_minutes(cooldown_at)
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
            "daily_calls_remaining": max(
                self.settings.llm_daily_call_limit - summary["today_calls"],
                0,
            ),
            "cooldown_remaining_minutes": cooldown,
            **summary,
        }

    def _cooldown_remaining_minutes(self, last_call_at: datetime | None) -> int:
        minimum_gap = max(self.settings.llm_min_minutes_between_calls, 0)
        if not minimum_gap or not last_call_at:
            return 0

        elapsed_seconds = (datetime.utcnow() - last_call_at).total_seconds()
        remaining_seconds = (minimum_gap * 60) - elapsed_seconds
        if remaining_seconds <= 0:
            return 0
        return int((remaining_seconds + 59) // 60)
