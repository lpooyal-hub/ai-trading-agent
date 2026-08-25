import json
import unittest
from urllib.error import HTTPError, URLError
from unittest.mock import MagicMock, patch

from app.clients.news_data_client import NewsDataClient
from app.config import Settings


class NewsDataClientTest(unittest.TestCase):
    def setUp(self):
        self.settings = Settings(
            _env_file=None,
            news_max_items_per_symbol=3,
            news_timeout_seconds=4,
        )
        self.client = NewsDataClient(self.settings)

    @staticmethod
    def _response(payload) -> MagicMock:
        response = MagicMock()
        response.read.return_value = json.dumps(payload).encode("utf-8")
        response.__enter__.return_value = response
        return response

    @staticmethod
    def _group(index: int) -> dict:
        return {
            "total": 5,
            "items": [
                {
                    "title": f"Headline {index}",
                    "body": f"Body {index}",
                    "officeName": f"Publisher {index}",
                    "datetime": f"2026-08-11T0{index}:00:00+09:00",
                    "mobileNewsUrl": f"https://n.news.naver.com/article/{index}",
                }
            ],
        }

    @patch("app.clients.news_data_client.request.urlopen")
    def test_successful_response_extracts_article_fields(self, urlopen):
        payload = [
            {
                "total": 2,
                "items": [
                    {
                        "title": "Samsung Electronics announces new product",
                        "body": "The company announced its latest product.",
                        "officeName": "Test News",
                        "datetime": "2026-08-11T09:15:00+09:00",
                        "mobileNewsUrl": "https://n.news.naver.com/article/001",
                    }
                ],
            },
            {
                "total": 2,
                "items": [
                    {
                        "title": "Semiconductor market outlook improves",
                        "body": "Demand forecasts were revised upward.",
                        "officeName": "Market Daily",
                        "datetime": "2026-08-11T08:30:00+09:00",
                        "mobileNewsUrl": "https://n.news.naver.com/article/002",
                    }
                ],
            },
        ]
        urlopen.return_value = self._response(payload)

        result = self.client.get_news("005930", limit=2)

        self.assertEqual(
            result,
            [
                {
                    "title": "Samsung Electronics announces new product",
                    "body": "The company announced its latest product.",
                    "source": "Test News",
                    "published_at": "2026-08-11T09:15:00+09:00",
                    "url": "https://n.news.naver.com/article/001",
                },
                {
                    "title": "Semiconductor market outlook improves",
                    "body": "Demand forecasts were revised upward.",
                    "source": "Market Daily",
                    "published_at": "2026-08-11T08:30:00+09:00",
                    "url": "https://n.news.naver.com/article/002",
                },
            ],
        )
        request_arg = urlopen.call_args.args[0]
        self.assertEqual(
            request_arg.full_url,
            "https://m.stock.naver.com/api/news/stock/005930?pageSize=2&page=1",
        )
        self.assertEqual(urlopen.call_args.kwargs["timeout"], 4)

    @patch("app.clients.news_data_client.request.urlopen")
    def test_limit_caps_articles_across_groups(self, urlopen):
        urlopen.return_value = self._response([self._group(index) for index in range(5)])

        result = self.client.get_news("005930", limit=2)

        self.assertEqual(len(result), 2)
        self.assertEqual(
            [article["title"] for article in result],
            ["Headline 0", "Headline 1"],
        )

    @patch("app.clients.news_data_client.request.urlopen")
    def test_items_without_title_are_skipped(self, urlopen):
        payload = [
            {
                "total": 3,
                "items": [
                    {"body": "Missing title"},
                    {"title": "", "body": "Empty title"},
                    {
                        "title": "Valid headline",
                        "body": "Valid body",
                        "officeName": "Test News",
                        "datetime": "2026-08-11T07:00:00+09:00",
                        "mobileNewsUrl": "https://n.news.naver.com/article/003",
                    },
                ],
            }
        ]
        urlopen.return_value = self._response(payload)

        result = self.client.get_news("005930")

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["title"], "Valid headline")

    @patch("app.clients.news_data_client.request.urlopen")
    def test_non_list_payload_returns_empty_list(self, urlopen):
        urlopen.return_value = self._response({"error": "unexpected response"})

        result = self.client.get_news("005930")

        self.assertEqual(result, [])

    def test_network_errors_return_empty_list(self):
        errors = [
            URLError("network unavailable"),
            TimeoutError("request timed out"),
            HTTPError(
                url="https://m.stock.naver.com/api/news/stock/005930",
                code=404,
                msg="Not Found",
                hdrs=None,
                fp=None,
            ),
        ]

        for network_error in errors:
            with self.subTest(error_type=type(network_error).__name__):
                with patch(
                    "app.clients.news_data_client.request.urlopen",
                    side_effect=network_error,
                ):
                    self.assertEqual(self.client.get_news("005930"), [])

    @patch("app.clients.news_data_client.request.urlopen")
    def test_invalid_json_returns_empty_list(self, urlopen):
        response = MagicMock()
        response.read.return_value = b"not valid json"
        response.__enter__.return_value = response
        urlopen.return_value = response

        result = self.client.get_news("005930")

        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()
