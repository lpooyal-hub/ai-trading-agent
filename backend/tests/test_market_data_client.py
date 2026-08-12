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
    def _settings(*, use_mock_data: bool, intraday_signals_enabled: bool = False) -> Settings:
        return Settings(
            _env_file=None,
            use_mock_data=use_mock_data,
            # These fields have validation aliases. Passing the aliases keeps
            # process environment values from leaking into test readiness.
            TOSS_API_KEY="fake-key",
            TOSS_SECRET_KEY="fake-secret",
            TOSS_TOKEN_PATH="/oauth2/token",
            TOSS_CANDLES_PATH="/api/v1/candles",
            TOSS_PRICES_PATH="/api/v1/prices",
            TOSS_ORDERBOOK_PATH="/api/v1/orderbook",
            intraday_signals_enabled=intraday_signals_enabled,
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
                    "price_mode": "daily_candle",
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

    def test_intraday_mode_batches_current_prices_and_uses_daily_reference(self):
        client = MarketDataClient(
            self._settings(use_mock_data=False, intraday_signals_enabled=True)
        )
        client.toss_client = self.toss_client
        self.toss_client.get_current_prices.return_value = {
            "success": True,
            "data": {
                "result": [
                    {"symbol": "005930", "lastPrice": "110,000", "timestamp": "2026-08-12T10:00:00+09:00"},
                    {"symbol": "035420", "lastPrice": "220,000", "timestamp": "2026-08-12T10:00:00+09:00"},
                ]
            },
        }
        self.toss_client.get_daily_candles.side_effect = [
            self._success_response([self._candle("2026-08-11T00:00:00+09:00", "100000")]),
            self._success_response([self._candle("2026-08-11T00:00:00+09:00", "200000")]),
        ]

        result = client.get_market_snapshots(["005930", "035420"])

        self.assertTrue(result.success)
        self.assertEqual([item["change_percent"] for item in result.snapshots], [10.0, 10.0])
        self.toss_client.get_current_prices.assert_called_once_with(["005930", "035420"])
        self.assertEqual(self.toss_client.get_daily_candles.call_count, 2)

    @patch("app.clients.market_data_client.time.monotonic", side_effect=[10.0, 10.0, 10.22, 10.22])
    @patch("app.clients.market_data_client.time.sleep")
    def test_intraday_context_fetches_candles_and_orderbook_for_shortlist(self, sleep_mock, _monotonic_mock):
        client = MarketDataClient(
            self._settings(use_mock_data=False, intraday_signals_enabled=True)
        )
        client.toss_client = self.toss_client
        self.toss_client.get_intraday_candles.return_value = self._success_response(
            [self._candle("2026-08-12T10:00:00+09:00", "110000")]
        )
        self.toss_client.get_orderbook.return_value = {
            "success": True,
            "data": {"result": {"bids": [{"price": "109900"}], "asks": [{"price": "110100"}]}},
        }

        contexts = client.get_intraday_context(["005930", "035420"])

        self.assertEqual(set(contexts), {"005930", "035420"})
        self.assertEqual(contexts["005930"]["bids"], [{"price": "109900"}])
        self.assertEqual(contexts["005930"]["asks"], [{"price": "110100"}])
        self.assertIsNone(contexts["005930"]["orderbook_timestamp"])
        self.assertEqual(self.toss_client.get_intraday_candles.call_count, 2)
        sleep_mock.assert_not_called()

    @patch("app.clients.market_data_client.time.monotonic", side_effect=[10.0, 10.0])
    @patch("app.clients.market_data_client.time.sleep")
    def test_intraday_context_propagates_the_orderbook_timestamp_when_present(self, _sleep_mock, _monotonic_mock):
        client = MarketDataClient(
            self._settings(use_mock_data=False, intraday_signals_enabled=True)
        )
        client.toss_client = self.toss_client
        self.toss_client.get_intraday_candles.return_value = self._success_response(
            [self._candle("2026-08-12T10:00:00+09:00", "110000")]
        )
        self.toss_client.get_orderbook.return_value = {
            "success": True,
            "data": {
                "result": {
                    "bids": [{"price": "109900"}],
                    "asks": [{"price": "110100"}],
                    "timestamp": "2026-08-12T10:00:05+09:00",
                }
            },
        }

        contexts = client.get_intraday_context(["005930"])

        self.assertEqual(contexts["005930"]["orderbook_timestamp"], "2026-08-12T10:00:05+09:00")

    @patch("app.clients.market_data_client.time.monotonic", return_value=10.0)
    @patch("app.clients.market_data_client.time.sleep")
    def test_intraday_context_only_calls_detail_apis_for_the_shortlist(self, _sleep_mock, _monotonic_mock):
        client = MarketDataClient(
            self._settings(use_mock_data=False, intraday_signals_enabled=True)
        )
        client.toss_client = self.toss_client
        self.assertEqual(client.settings.intraday_shortlist_size_safe, 6)
        self.toss_client.get_intraday_candles.return_value = self._success_response(
            [self._candle("2026-08-12T10:00:00+09:00", "110000")]
        )
        self.toss_client.get_orderbook.return_value = {
            "success": True,
            "data": {"result": {"bids": [], "asks": []}},
        }
        full_universe = ["005930", "035420", "000270", "373220", "207940", "035720", "005490", "068270"]

        contexts = client.get_intraday_context(full_universe)

        self.assertEqual(set(contexts), set(full_universe[:6]))
        self.assertEqual(self.toss_client.get_intraday_candles.call_count, 6)
        self.assertEqual(self.toss_client.get_orderbook.call_count, 6)
        self.toss_client.get_intraday_candles.assert_any_call("005930", count=30)
        called_symbols = {call_args.args[0] for call_args in self.toss_client.get_intraday_candles.call_args_list}
        self.assertNotIn("005490", called_symbols)
        self.assertNotIn("068270", called_symbols)

    def test_daily_reference_is_cached_and_not_refetched_within_the_same_market_day(self):
        client = MarketDataClient(
            self._settings(use_mock_data=False, intraday_signals_enabled=True)
        )
        client.toss_client = self.toss_client
        self.toss_client.get_current_prices.return_value = {
            "success": True,
            "data": {
                "result": [
                    {"symbol": "005930", "lastPrice": "110,000", "timestamp": "2026-08-12T10:00:00+09:00"},
                ]
            },
        }
        self.toss_client.get_daily_candles.return_value = self._success_response(
            [self._candle("2026-08-11T00:00:00+09:00", "100000")]
        )

        first = client.get_market_snapshots(["005930"])
        second = client.get_market_snapshots(["005930"])

        self.assertTrue(first.success)
        self.assertTrue(second.success)
        self.toss_client.get_daily_candles.assert_called_once_with("005930", count=2)


if __name__ == "__main__":
    unittest.main()
