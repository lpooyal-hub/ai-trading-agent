import json
from urllib import error, parse, request

from app.config import Settings, get_settings


class NewsDataClient:
    """Real per-symbol news headlines via Naver's public mobile stock-news
    API (https://m.stock.naver.com/api/news/stock/{code}) -- unofficial,
    no auth required. Response is a list of groups, each with an "items"
    list (usually one article per group); this flattens and takes the
    newest `limit` articles.

    Fails soft: any network/parse error returns an empty list rather than
    raising, since news is supplementary context for the decision prompt,
    not something that should ever block a trading cycle.
    """

    provider_name = "naver_news"
    base_url = "https://m.stock.naver.com/api/news/stock/"

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    def get_news(self, symbol: str, limit: int | None = None) -> list[dict]:
        limit = limit or self.settings.news_max_items_per_symbol
        url = f"{self.base_url}{parse.quote(symbol)}?pageSize={limit}&page=1"
        req = request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        try:
            with request.urlopen(req, timeout=self.settings.news_timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (error.HTTPError, error.URLError, TimeoutError, json.JSONDecodeError, ValueError, OSError):
            return []

        if not isinstance(payload, list):
            return []

        items: list[dict] = []
        for group in payload:
            if not isinstance(group, dict):
                continue
            for item in group.get("items", []):
                if not isinstance(item, dict) or not item.get("title"):
                    continue
                items.append(
                    {
                        "title": item.get("title", ""),
                        "body": item.get("body", ""),
                        "source": item.get("officeName", ""),
                        "published_at": item.get("datetime", ""),
                        "url": item.get("mobileNewsUrl", ""),
                    }
                )
                if len(items) >= limit:
                    return items
        return items
