import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.config import Settings
from app.worker import (
    run_agent_session,
    run_worker,
    wait_until_market_close,
    wait_until_market_open,
)


class _StopLoop(Exception):
    """Raised by test doubles to break run_worker's `while True` after N iterations."""


class WorkerPacingTest(unittest.TestCase):
    def setUp(self):
        self.settings = Settings(
            _env_file=None,
            dry_run=True,
            live_trading_enabled=False,
            use_mock_data=True,
            agent_scheduler_enabled=True,
        )

    def test_wait_until_market_open_polls_until_market_opens(self):
        sleeps: list[float] = []

        with patch("app.worker.is_market_open", side_effect=[False, False, True]):
            wait_until_market_open(self.settings, poll_seconds=5, sleep_fn=sleeps.append)

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

    def test_run_worker_idles_without_running_sessions_when_scheduler_disabled(self):
        self.settings.agent_scheduler_enabled = False

        def sleep_and_stop(_seconds):
            raise _StopLoop

        with patch("app.worker.AgentGraphService") as graph_service_cls, \
                patch("app.worker.wait_until_market_open") as wait_open, \
                patch("app.worker.run_agent_session") as run_session:
            with self.assertRaises(_StopLoop):
                run_worker(self.settings, sleep_fn=sleep_and_stop)

        wait_open.assert_not_called()
        run_session.assert_not_called()
        graph_service_cls.assert_called_once()

    def test_run_worker_runs_one_session_per_market_day_when_enabled(self):
        session = SimpleNamespace(id=1, status=SimpleNamespace(value="SUCCEEDED"), cycle_count=3, stop_reason="done")

        def close_and_stop(_settings, sleep_fn):
            raise _StopLoop

        with patch("app.worker.AgentGraphService"), \
                patch("app.worker.wait_until_market_open") as wait_open, \
                patch("app.worker.run_agent_session", return_value=session) as run_session, \
                patch("app.worker.wait_until_market_close", side_effect=close_and_stop) as wait_close:
            with self.assertRaises(_StopLoop):
                run_worker(self.settings, sleep_fn=lambda _seconds: None)

        wait_open.assert_called_once()
        run_session.assert_called_once()
        wait_close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
