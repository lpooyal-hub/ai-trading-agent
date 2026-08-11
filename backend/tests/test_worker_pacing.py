import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.config import Settings
from app.worker import (
    run_agent_session,
    wait_until_market_close,
    wait_until_session_start,
    worker_can_start_session,
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

    def test_worker_stays_inert_when_scheduler_is_disabled(self):
        self.settings.agent_scheduler_enabled = False

        with patch("app.worker.is_market_open") as market_open:
            allowed = worker_can_start_session(self.settings)

        self.assertFalse(allowed)
        market_open.assert_not_called()

    def test_wait_until_session_start_polls_until_market_opens(self):
        sleeps: list[float] = []

        with patch("app.worker.is_market_open", side_effect=[False, False, True]):
            wait_until_session_start(self.settings, poll_seconds=5, sleep_fn=sleeps.append)

        self.assertEqual([5.0, 5.0], sleeps)

    def test_wait_until_market_close_polls_while_market_is_open(self):
        sleeps: list[float] = []

        with patch("app.worker.is_market_open", side_effect=[True, True, False]):
            wait_until_market_close(self.settings, poll_seconds=7, sleep_fn=sleeps.append)

        self.assertEqual([7.0, 7.0], sleeps)

    @patch("app.worker.SessionLocal")
    def test_run_agent_session_uses_worker_trigger_source(self, session_local):
        db = object()
        session_local.return_value.__enter__.return_value = db
        expected = SimpleNamespace(id=1)
        graph_service = Mock()
        graph_service.run_session.return_value = expected

        actual = run_agent_session(graph_service)

        self.assertIs(expected, actual)
        graph_service.run_session.assert_called_once_with(db, trigger_source="worker")


if __name__ == "__main__":
    unittest.main()
