import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import Mock

from app.config import Settings
from app.services.agent_graph_service import AgentGraphService


class AgentGraphSessionStopTest(unittest.TestCase):
    def test_llm_daily_limit_does_not_stop_market_and_position_monitoring(self):
        service = AgentGraphService.__new__(AgentGraphService)
        llm_budget_manager = Mock()
        llm_budget_manager.check_budget.return_value = {
            "approved": False,
            "reason": "Daily LLM call limit reached.",
        }
        risk_manager = Mock()
        risk_manager.count_today_simulated_trades.return_value = 0
        service.agent = SimpleNamespace(
            llm_budget_manager=llm_budget_manager,
            execution_risk_agent=SimpleNamespace(risk_manager=risk_manager),
        )
        settings = Settings(
            _env_file=None,
            agent_scheduler_market_hours_only=False,
            agent_session_max_minutes=480,
            max_daily_trades=0,
        )
        session = SimpleNamespace(
            stop_requested=False,
            cycle_count=1,
            max_cycles=100,
            started_at=datetime.utcnow(),
        )

        reason = service._session_stop_reason(object(), session, settings)

        self.assertIsNone(reason)
        llm_budget_manager.check_budget.assert_not_called()
        risk_manager.count_today_simulated_trades.assert_called_once()


if __name__ == "__main__":
    unittest.main()
