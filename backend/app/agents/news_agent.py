from dataclasses import dataclass

from app.clients.news_data_client import NewsDataClient
from app.config import Settings, get_settings
from app.models import MarketSnapshot


@dataclass
class NewsAgentResult:
    items: list[dict]
    summary: str
    source: str


class NewsAgent:
    """News/event context layer for decision input.

    Fetches real per-symbol headlines (see NewsDataClient, Naver's public
    stock-news API) for each candidate, alongside a deterministic price/
    volume signal that's always available even if the news fetch fails or
    returns nothing for a symbol (fails soft, never blocks a cycle).

    Only called with the already rule-filtered candidates (at most
    llm_max_candidates_per_run), not the whole active universe -- see the
    market_agent -> news_agent wiring in agent_service.py /
    agent_graph_service.py. Fetching news for the full universe (tens of
    symbols) every cycle would be unnecessary load on an unofficial public
    endpoint for symbols that were never going to reach the LLM anyway.
    """

    def __init__(self, settings: Settings | None = None, news_client: NewsDataClient | None = None):
        self.settings = settings or get_settings()
        self.news_client = news_client or NewsDataClient(self.settings)

    def run(self, candidates: list[MarketSnapshot]) -> NewsAgentResult:
        items = [self._symbol_context(snapshot) for snapshot in candidates]
        has_real_news = any(item["headlines"] for item in items)
        return NewsAgentResult(
            items=items,
            summary=self._summary(items),
            source=self.news_client.provider_name if has_real_news else "snapshot_event_context",
        )

    def _symbol_context(self, snapshot: MarketSnapshot) -> dict:
        headlines = self.news_client.get_news(snapshot.symbol)
        direction = "positive" if snapshot.change_percent > 0 else "negative" if snapshot.change_percent < 0 else "neutral"
        magnitude = "large" if abs(snapshot.change_percent) >= 2 else "moderate" if abs(snapshot.change_percent) >= 0.75 else "small"
        volume_signal = "high_volume" if snapshot.volume >= 1_500_000 else "normal_volume"
        summary = (
            f"{snapshot.symbol} shows {magnitude} {direction} price movement "
            f"({snapshot.change_percent:.2f}%) with {volume_signal.replace('_', ' ')}."
        )
        if headlines:
            summary = f"{summary} Recent headline: {headlines[0]['title']}"
        return {
            "symbol": snapshot.symbol,
            "event_type": "market_snapshot",
            "sentiment": direction,
            "magnitude": magnitude,
            "volume_signal": volume_signal,
            "headlines": headlines,
            "summary": summary,
            "source": snapshot.extra_json.get("source", "market_snapshot"),
        }

    @staticmethod
    def _summary(items: list[dict]) -> str:
        if not items:
            return "No news or event context is available."
        positives = sum(1 for item in items if item["sentiment"] == "positive")
        negatives = sum(1 for item in items if item["sentiment"] == "negative")
        high_volume = sum(1 for item in items if item["volume_signal"] == "high_volume")
        headline_count = sum(len(item["headlines"]) for item in items)
        return (
            f"Snapshot context covers {len(items)} symbols: "
            f"{positives} positive, {negatives} negative, {high_volume} high-volume signals, "
            f"{headline_count} real news headlines fetched."
        )
