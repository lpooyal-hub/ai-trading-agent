import unittest

from app.config import Settings


KRX_REGULAR_SESSION_MINUTES = (15 * 60 + 30) - (9 * 60)  # 09:00-15:30 -> 390 minutes
RECOMMENDED_INTRADAY_INTERVAL_MINUTES = 5


class SessionCoverageTest(unittest.TestCase):
    def test_default_session_cycles_cover_a_full_krx_session_at_the_recommended_intraday_interval(self):
        settings = Settings(_env_file=None)

        max_session_minutes_from_cycles = (
            settings.agent_session_max_cycles_safe * RECOMMENDED_INTRADAY_INTERVAL_MINUTES
        )

        self.assertGreaterEqual(max_session_minutes_from_cycles, KRX_REGULAR_SESSION_MINUTES)

    def test_max_cycles_is_not_the_binding_stop_condition_at_the_recommended_interval(self):
        # agent_session_max_minutes and the market-close check must remain the
        # real stop guards; max_cycles should only be a generous outer bound,
        # not something a normal trading day actually runs into.
        settings = Settings(_env_file=None)

        max_session_minutes_from_cycles = (
            settings.agent_session_max_cycles_safe * RECOMMENDED_INTRADAY_INTERVAL_MINUTES
        )

        self.assertGreaterEqual(
            max_session_minutes_from_cycles,
            settings.agent_session_max_minutes_safe,
        )


if __name__ == "__main__":
    unittest.main()
