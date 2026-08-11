import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.config import Settings
from app.worker import (
    run_agent_session,
    run_worker_once,
    wait_for_todays_market_open,
)


class WorkerPacingTest(unittest.TestCase):
    def setUp(self):
        self.settings = Settings(
            _env_file=None,
            dry_run=True,
            live_trading_enabled=False,
            use_mock_data=True,
            agent_scheduler_enabled=True,
        )

    def test_wait_for_todays_market_open_polls_until_open(self):
        sleeps: list[float] = []
        windows = [
            {"open_now": False, "session": "PRE_MARKET"},
            {"open_now": False, "session": "PRE_MARKET"},
            {"open_now": True, "session": "REGULAR"},
        ]

        with patch("app.worker.get_market_window", side_effect=windows):
            opened = wait_for_todays_market_open(self.settings, poll_seconds=5, sleep_fn=sleeps.append)

        self.assertTrue(opened)
        self.assertEqual([5.0, 5.0], sleeps)

    def test_wait_for_todays_market_open_gives_up_on_terminal_session(self):
        sleeps: list[float] = []
        windows = [
            {"open_now": False, "session": "PRE_MARKET"},
            {"open_now": False, "session": "MARKET_CLOSED_DATE"},
        ]

        with patch("app.worker.get_market_window", side_effect=windows):
            opened = wait_for_todays_market_open(self.settings, poll_seconds=5, sleep_fn=sleeps.append)

        self.assertFalse(opened)
        self.assertEqual([5.0], sleeps)

    def test_run_agent_session_uses_worker_trigger_source(self):
        with patch("app.worker.SessionLocal") as session_local:
            db = object()
            session_local.return_value.__enter__.return_value = db
            expected = SimpleNamespace(id=1)
            graph_service = Mock()
            graph_service.run_session.return_value = expected

            actual = run_agent_session(graph_service)

        self.assertIs(expected, actual)
        graph_service.run_session.assert_called_once_with(db, trigger_source="worker")

    def test_run_worker_once_is_inert_when_scheduler_disabled(self):
        self.settings.agent_scheduler_enabled = False

        with patch("app.worker.wait_for_todays_market_open") as wait_open, \
                patch("app.worker.AgentGraphService") as graph_service_cls:
            run_worker_once(self.settings)

        wait_open.assert_not_called()
        graph_service_cls.assert_not_called()

    def test_run_worker_once_skips_session_when_market_never_opens_today(self):
        with patch("app.worker.wait_for_todays_market_open", return_value=False) as wait_open, \
                patch("app.worker.AgentGraphService") as graph_service_cls:
            run_worker_once(self.settings)

        wait_open.assert_called_once()
        graph_service_cls.assert_not_called()

    def test_run_worker_once_runs_a_single_session_when_market_opens(self):
        session = SimpleNamespace(id=1, status=SimpleNamespace(value="SUCCEEDED"), cycle_count=3, stop_reason="done")

        with patch("app.worker.wait_for_todays_market_open", return_value=True), \
                patch("app.worker.run_agent_session", return_value=session) as run_session:
            run_worker_once(self.settings)

        run_session.assert_called_once()


if __name__ == "__main__":
    unittest.main()
