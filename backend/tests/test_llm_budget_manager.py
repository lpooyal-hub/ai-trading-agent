from datetime import datetime
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from app.config import Settings
from app.risk.llm_budget_manager import LLMBudgetManager


class LLMBudgetManagerTest(unittest.TestCase):
    def setUp(self):
        settings = Settings(
            _env_file=None,
            llm_daily_cost_limit_usd=1,
            llm_monthly_cost_limit_usd=10,
            llm_daily_token_limit=100000,
            llm_daily_call_limit=10,
            llm_min_minutes_between_calls=60,
        )
        self.manager = LLMBudgetManager(settings)
        self.manager.usage_service = Mock()
        self.manager.usage_service.summarize.return_value = {
            "today_calls": 1,
            "today_prompt_tokens": 100,
            "today_completion_tokens": 20,
            "today_total_tokens": 120,
            "today_estimated_cost_usd": 0.01,
            "monthly_estimated_cost_usd": 0.01,
            "average_latency_ms": 100,
            "successful_calls": 1,
            "failed_calls": 0,
            "last_call_at": datetime.utcnow(),
        }
        self.manager.usage_service.latest_usage_for_cooldown.return_value = SimpleNamespace(
            created_at=datetime.utcnow(),
        )

    def test_cooldown_blocks_a_new_llm_call(self):
        result = self.manager.check_budget(object())

        self.assertFalse(result["approved"])
        self.assertIn("cooldown", result["reason"])

    def test_session_stop_check_can_ignore_only_the_cooldown(self):
        result = self.manager.check_budget(object(), include_cooldown=False)

        self.assertTrue(result["approved"])
        self.assertEqual(result["reason"], "LLM budget available.")


if __name__ == "__main__":
    unittest.main()
