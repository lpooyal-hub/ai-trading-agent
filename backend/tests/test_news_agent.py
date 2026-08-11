import unittest
from unittest.mock import Mock, call

from app.agents.news_agent import NewsAgent
from app.config import Settings
from app.models import MarketSnapshot


class NewsAgentTest(unittest.TestCase):
    def setUp(self):
        self.news_client = Mock()
        self.news_client.provider_name = "test_news_provider"
        self.agent = NewsAgent(
            Settings(_env_file=None),
            news_client=self.news_client,
        )

    @staticmethod
    def _candidate(
        symbol: str,
        *,
        change_percent: float = 1.0,
        volume: float = 1_000_000,
    ) -> MarketSnapshot:
        return MarketSnapshot(
            symbol=symbol,
            price=70_000,
            change_percent=change_percent,
            volume=volume,
            sector="semiconductor",
            extra_json={"source": "test_snapshot"},
        )

    def test_empty_candidates_return_no_context(self):
        result = self.agent.run([])

        self.assertEqual(result.items, [])
        self.assertEqual(result.summary, "No news or event context is available.")
        self.assertEqual(result.source, "snapshot_event_context")
        self.news_client.get_news.assert_not_called()

    def test_real_headlines_are_included_in_item_summary_and_result_source(self):
        headlines = [
            {
                "title": "Semiconductor demand forecast rises",
                "body": "Demand is expected to improve.",
                "source": "Test News",
                "published_at": "2026-08-11T09:15:00+09:00",
                "url": "https://n.news.naver.com/article/001",
            }
        ]
        self.news_client.get_news.return_value = headlines

        result = self.agent.run([self._candidate("005930")])

        self.assertEqual(result.items[0]["headlines"], headlines)
        self.assertIn(
            "Recent headline: Semiconductor demand forecast rises",
            result.items[0]["summary"],
        )
        self.assertEqual(result.source, self.news_client.provider_name)

    def test_no_headlines_falls_back_to_snapshot_signals(self):
        self.news_client.get_news.return_value = []

        result = self.agent.run(
            [
                self._candidate(
                    "005930",
                    change_percent=2.5,
                    volume=1_500_000,
                )
            ]
        )

        item = result.items[0]
        self.assertEqual(result.source, "snapshot_event_context")
        self.assertEqual(item["headlines"], [])
        self.assertEqual(item["sentiment"], "positive")
        self.assertEqual(item["magnitude"], "large")
        self.assertEqual(item["volume_signal"], "high_volume")

    def test_news_client_is_called_once_for_each_candidate_symbol(self):
        self.news_client.get_news.return_value = []
        candidates = [
            self._candidate("005930"),
            self._candidate("035420"),
            self._candidate("000270"),
        ]

        self.agent.run(candidates)

        self.news_client.get_news.assert_has_calls(
            [call("005930"), call("035420"), call("000270")]
        )
        self.assertEqual(self.news_client.get_news.call_count, 3)


if __name__ == "__main__":
    unittest.main()
