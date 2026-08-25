import json
import unittest
from unittest.mock import MagicMock, patch
from urllib.parse import unquote

from app.clients.toss_client import TossClient, _READ_CACHE
from app.config import Settings


class TossClientTest(unittest.TestCase):
    def setUp(self):
        _READ_CACHE.clear()
        self.addCleanup(_READ_CACHE.clear)
        self.settings = Settings(
            _env_file=None,
            use_mock_data=False,
            TOSS_API_KEY="fake-key",
            TOSS_SECRET_KEY="fake-secret",
            TOSS_TOKEN_PATH="/oauth2/token",
            TOSS_CANDLES_PATH="/api/v1/candles",
            TOSS_PRICES_PATH="/api/v1/prices",
            TOSS_ORDERBOOK_PATH="/api/v1/orderbook",
            toss_read_cache_ttl_seconds=0,
        )
        self.client = TossClient(self.settings)

    @staticmethod
    def _mock_response(payload: dict):
        response = MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = json.dumps(payload).encode("utf-8")
        return response

    @staticmethod
    def _token_response():
        return TossClientTest._mock_response({"access_token": "tok", "expires_in": 300})

    @patch("app.clients.toss_client.request.urlopen")
    def test_get_current_prices_batches_symbols_into_one_query(self, urlopen_mock):
        urlopen_mock.side_effect = [self._token_response(), self._mock_response({"result": []})]

        result = self.client.get_current_prices(["005930", "035420"])

        self.assertTrue(result["success"])
        requested_url = urlopen_mock.call_args_list[1].args[0].full_url
        self.assertIn("/api/v1/prices?", requested_url)
        self.assertIn("symbols=005930", unquote(requested_url))
        self.assertIn("005930,035420", unquote(requested_url))

    @patch("app.clients.toss_client.request.urlopen")
    def test_get_current_prices_caps_at_two_hundred_symbols(self, urlopen_mock):
        urlopen_mock.side_effect = [self._token_response(), self._mock_response({"result": []})]
        many_symbols = [f"{i:06d}" for i in range(250)]

        self.client.get_current_prices(many_symbols)

        requested_url = urlopen_mock.call_args_list[1].args[0].full_url
        decoded = unquote(requested_url)
        symbol_count = decoded.split("symbols=")[1].count(",") + 1
        self.assertEqual(symbol_count, 200)

    @patch("app.clients.toss_client.request.urlopen")
    def test_get_current_prices_with_no_symbols_short_circuits_without_a_call(self, urlopen_mock):
        result = self.client.get_current_prices([])

        self.assertTrue(result["success"])
        self.assertEqual(result["data"], {"result": []})
        urlopen_mock.assert_not_called()

    @patch("app.clients.toss_client.request.urlopen")
    def test_get_intraday_candles_requests_a_one_minute_interval(self, urlopen_mock):
        urlopen_mock.side_effect = [
            self._token_response(),
            self._mock_response({"result": {"candles": []}}),
        ]

        self.client.get_intraday_candles("005930", count=30)

        requested_url = urlopen_mock.call_args_list[1].args[0].full_url
        self.assertIn("interval=1m", requested_url)
        self.assertIn("count=30", requested_url)

    @patch("app.clients.toss_client.request.urlopen")
    def test_get_intraday_candles_clamps_count_to_a_safe_range(self, urlopen_mock):
        urlopen_mock.side_effect = [
            self._token_response(),
            self._mock_response({"result": {"candles": []}}),
        ]

        self.client.get_intraday_candles("005930", count=10000)

        requested_url = urlopen_mock.call_args_list[1].args[0].full_url
        self.assertIn("count=200", requested_url)

    @patch("app.clients.toss_client.request.urlopen")
    def test_get_orderbook_requests_the_orderbook_path(self, urlopen_mock):
        urlopen_mock.side_effect = [
            self._token_response(),
            self._mock_response({"result": {"bids": [], "asks": []}}),
        ]

        self.client.get_orderbook("005930")

        requested_url = urlopen_mock.call_args_list[1].args[0].full_url
        self.assertTrue(requested_url.startswith(f"{self.settings.toss_base_url}/api/v1/orderbook"))

    @patch("app.clients.toss_client.request.urlopen")
    def test_access_token_is_reused_across_multiple_read_only_calls(self, urlopen_mock):
        urlopen_mock.side_effect = [
            self._token_response(),
            self._mock_response({"result": []}),
            self._mock_response({"result": {"candles": []}}),
        ]

        self.client.get_current_prices(["005930"])
        self.client.get_intraday_candles("005930")

        token_calls = [
            call for call in urlopen_mock.call_args_list
            if call.args[0].full_url.endswith("/oauth2/token")
        ]
        self.assertEqual(len(token_calls), 1)

    def test_not_configured_returns_todo_without_a_network_call(self):
        client = TossClient(Settings(_env_file=None, use_mock_data=True))

        result = client.get_current_prices(["005930"])

        self.assertFalse(result["success"])
        self.assertEqual(result["status"], "TODO_READ_ONLY_API_NOT_CONFIGURED")


if __name__ == "__main__":
    unittest.main()
