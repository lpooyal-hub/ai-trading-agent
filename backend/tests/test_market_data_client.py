import unittest
from unittest.mock import call, patch

from app.clients.market_data_client import MarketDataClient
from app.config import Settings


class MarketDataClientTest(unittest.TestCase):
    def setUp(self):
        self.settings = self._settings(use_mock_data=False)
        self.toss_client_patcher = patch("app.clients.market_data_client.TossClient")
        toss_client_class = self.toss_client_patcher.start()
        self.addCleanup(self.toss_client_patcher.stop)
        self.toss_client = toss_client_class.return_value
        self.client = MarketDataClient(self.settings)

        self.assertTrue(self.settings.toss_market_data_ready)

    @staticmethod
    def _settings(*, use_mock_data: bool) -> Settings:
        return Settings(
            _env_file=None,
            use_mock_data=use_mock_data,
            # These fields have validation aliases. Passing the aliases keeps
            # process environment values from leaking into test readiness.
            TOSS_API_KEY="fake-key",
            TOSS_SECRET_KEY="fake-secret",
            TOSS_TOKEN_PATH="/oauth2/token",
            TOSS_CANDLES_PATH="/api/v1/candles",
        )

    @staticmethod
    def _candle(timestamp: str, close_price: str, volume: str = "1,234,567") -> dict:
        return {
            "timestamp": timestamp,
            "openPrice": close_price,
            "highPrice": close_price,
            "lowPrice": close_price,
            "closePrice": close_price,
            "volume": volume,
        }

    @staticmethod
    def _success_response(candles: list[dict]) -> dict:
        # Mirrors the live Toss envelope returned by /api/v1/candles.
        return {
            "success": True,
            "data": {
                "result": {
                    "candles": candles,
                }
            },
        }

    def test_successful_response_parses_latest_price_change_volume_and_sector(self):
        self.toss_client.get_daily_candles.return_value = self._success_response(
            [
                self._candle("2026-08-11T00:00:00+09:00", "110,000", "2,500,000"),
                self._candle("2026-08-10T00:00:00+09:00", "100,000", "1,900,000"),
            ]
        )

        result = self.client.get_market_snapshots(["005930"])

        self.assertTrue(result.success)
        self.assertEqual(result.status, "OK")
        self.assertEqual(len(result.snapshots), 1)
        self.assertEqual(
            result.snapshots[0],
            {
                "symbol": "005930",
                "price": 110000.0,
                "change_percent": 10.0,
                "volume": 2500000.0,
                "sector": "semiconductor",
                "extra_json": {
                    "source": "toss_securities",
                    "raw": self.toss_client.get_daily_candles.return_value["data"],
                },
            },
        )
        self.toss_client.get_daily_candles.assert_called_once_with("005930", count=2)

    def test_candles_are_sorted_by_timestamp_before_change_is_calculated(self):
        self.toss_client.get_daily_candles.return_value = self._success_response(
            [
                # Deliberately oldest-first. Trusting array position would
                # regress to price=100000 and change_percent=-9.0909 here.
                self._candle("2026-08-10T00:00:00+09:00", "100000", "1,900,000"),
                self._candle("2026-08-11T00:00:00+09:00", "110000", "2,500,000"),
            ]
        )

        result = self.client.get_market_snapshots(["005930"])

        self.assertTrue(result.success)
        self.assertEqual(result.snapshots[0]["price"], 110000.0)
        self.assertEqual(result.snapshots[0]["change_percent"], 10.0)
        self.assertEqual(result.snapshots[0]["volume"], 2500000.0)

    def test_not_configured_does_not_call_toss(self):
        client = MarketDataClient(self._settings(use_mock_data=True))
        self.assertFalse(client.settings.toss_market_data_ready)

        result = client.get_market_snapshots(["005930"])

        self.assertFalse(result.success)
        self.assertEqual(result.status, "NOT_CONFIGURED")
        self.assertEqual(result.snapshots, [])
        self.toss_client.get_daily_candles.assert_not_called()

    def test_partial_symbol_failure_returns_successful_snapshots_and_error_message(self):
        responses = {
            "005930": self._success_response(
                [self._candle("2026-08-11T00:00:00+09:00", "110000")]
            ),
            "035420": {"success": False, "message": "temporary upstream error"},
            "000270": self._success_response(
                [self._candle("2026-08-11T00:00:00+09:00", "85000")]
            ),
        }
        self.toss_client.get_daily_candles.side_effect = (
            lambda symbol, count: responses[symbol]
        )

        result = self.client.get_market_snapshots(["005930", "035420", "000270"])

        self.assertTrue(result.success)
        self.assertEqual(result.status, "OK")
        self.assertEqual(
            [snapshot["symbol"] for snapshot in result.snapshots],
            ["005930", "000270"],
        )
        self.assertIn("035420", result.message)
        self.assertIn("temporary upstream error", result.message)
        self.toss_client.get_daily_candles.assert_has_calls(
            [
                call("005930", count=2),
                call("035420", count=2),
                call("000270", count=2),
            ]
        )

    def test_all_symbol_failures_return_fetch_failed(self):
        self.toss_client.get_daily_candles.return_value = {
            "success": False,
            "message": "Toss unavailable",
        }

        result = self.client.get_market_snapshots(["005930", "035420"])

        self.assertFalse(result.success)
        self.assertEqual(result.status, "FETCH_FAILED")
        self.assertEqual(result.snapshots, [])
        self.assertIn("005930", result.message)
        self.assertIn("035420", result.message)
        self.assertEqual(self.toss_client.get_daily_candles.call_count, 2)

    def test_single_candle_uses_zero_change_percent(self):
        self.toss_client.get_daily_candles.return_value = self._success_response(
            [self._candle("2026-08-11T00:00:00+09:00", "110000")]
        )

        result = self.client.get_market_snapshots(["005930"])

        self.assertTrue(result.success)
        self.assertEqual(result.snapshots[0]["price"], 110000.0)
        self.assertEqual(result.snapshots[0]["change_percent"], 0.0)


if __name__ == "__main__":
    unittest.main()
