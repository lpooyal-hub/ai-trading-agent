import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace

from app.agents.market_agent import MarketAgent
from app.config import Settings


def _snapshot(
    *,
    symbol: str,
    created_at: datetime,
    event_triggered: bool = True,
    score: float = 3.0,
) -> SimpleNamespace:
    return SimpleNamespace(
        symbol=symbol,
        created_at=created_at,
        change_percent=1.0,
        volume=1000.0,
        extra_json={
            "intraday_signal": {
                "score": score,
                "reason": "5m/15m return 1.20%/1.80%",
                "return_5m_percent": 1.2,
                "return_15m_percent": 1.8,
                "volume_ratio": 2.5,
                "vwap_deviation_percent": 0.4,
                "spread_percent": 0.2,
                "event_triggered": event_triggered,
            }
        },
    )


class MarketAgentStoredIntradayResultTest(unittest.TestCase):
    def setUp(self):
        self.settings = Settings(
            _env_file=None,
            use_mock_data=True,
            intraday_signals_enabled=True,
            agent_scheduler_interval_minutes=5,
            market_snapshot_max_age_minutes=30,
        )
        self.agent = MarketAgent(self.settings)

    def test_fresh_triggered_signal_is_returned_as_a_candidate(self):
        snapshot = _snapshot(symbol="005930", created_at=datetime.utcnow())

        result = self.agent._stored_intraday_result([snapshot], {})

        self.assertEqual(len(result.candidates), 1)
        self.assertEqual(result.candidate_details[0]["symbol"], "005930")

    def test_stale_triggered_signal_is_excluded_even_within_the_general_freshness_window(self):
        # agent_scheduler_interval_minutes=5 -> intraday cutoff is 15 minutes
        # (3x cadence), well inside the general 30-minute freshness window
        # market_snapshot_max_age_minutes still allows through.
        stale_snapshot = _snapshot(
            symbol="005930",
            created_at=datetime.utcnow() - timedelta(minutes=20),
        )

        result = self.agent._stored_intraday_result([stale_snapshot], {})

        self.assertEqual(result.candidates, [])

    def test_untriggered_signal_is_not_a_candidate(self):
        snapshot = _snapshot(symbol="005930", created_at=datetime.utcnow(), event_triggered=False)

        result = self.agent._stored_intraday_result([snapshot], {})

        self.assertEqual(result.candidates, [])

    def test_candidates_are_ranked_by_score_before_truncation(self):
        settings = Settings(
            _env_file=None,
            use_mock_data=True,
            intraday_signals_enabled=True,
            agent_scheduler_interval_minutes=5,
            market_snapshot_max_age_minutes=30,
            llm_max_candidates_per_run=1,
        )
        agent = MarketAgent(settings)
        now = datetime.utcnow()
        # Deliberately listed weakest-first: active_universe iteration order
        # has no relationship to signal strength, so the fix must not rely on
        # input order to surface the strongest candidate.
        weak = _snapshot(symbol="005930", created_at=now, score=1.0)
        strong = _snapshot(symbol="000660", created_at=now, score=9.0)

        result = agent._stored_intraday_result([weak, strong], {})

        self.assertEqual(len(result.candidates), 1)
        self.assertEqual(result.candidate_details[0]["symbol"], "000660")

    def test_shortlist_fallback_never_reintroduces_held_symbol_outside_universe(self):
        outside = _snapshot(symbol="999999", created_at=datetime.utcnow())
        outside.change_percent = 99
        outside.volume = 99_000_000
        inside = _snapshot(symbol=self.settings.active_universe[0], created_at=datetime.utcnow())
        inside.change_percent = 0

        symbols = self.agent._intraday_shortlist_symbols([outside, inside])

        self.assertNotIn("999999", symbols)


if __name__ == "__main__":
    unittest.main()
