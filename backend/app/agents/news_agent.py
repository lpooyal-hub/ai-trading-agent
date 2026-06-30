from dataclasses import dataclass

from app.config import Settings, get_settings
from app.models import MarketSnapshot


@dataclass
class NewsAgentResult:
    items: list[dict]
    summary: str
    source: str


class NewsAgent:
    """Build a safe news/context layer for decision input.

    External news collection is intentionally not connected yet. For now this
    agent derives deterministic market-event context from fresh snapshots, so
    the downstream Decision Agent already has a stable news_context contract.
    """

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    def run(self, snapshots: list[MarketSnapshot]) -> NewsAgentResult:
        items = [self._snapshot_context(snapshot) for snapshot in snapshots]
        return NewsAgentResult(
            items=items,
            summary=self._summary(items),
            source="snapshot_event_context",
        )

    @staticmethod
    def _snapshot_context(snapshot: MarketSnapshot) -> dict:
        direction = "positive" if snapshot.change_percent > 0 else "negative" if snapshot.change_percent < 0 else "neutral"
        magnitude = "large" if abs(snapshot.change_percent) >= 2 else "moderate" if abs(snapshot.change_percent) >= 0.75 else "small"
        volume_signal = "high_volume" if snapshot.volume >= 1_500_000 else "normal_volume"
        return {
            "symbol": snapshot.symbol,
            "event_type": "market_snapshot",
            "sentiment": direction,
            "magnitude": magnitude,
            "volume_signal": volume_signal,
            "summary": (
                f"{snapshot.symbol} shows {magnitude} {direction} price movement "
                f"({snapshot.change_percent:.2f}%) with {volume_signal.replace('_', ' ')}."
            ),
            "source": snapshot.extra_json.get("source", "market_snapshot"),
        }

    @staticmethod
    def _summary(items: list[dict]) -> str:
        if not items:
            return "No news or event context is available."
        positives = sum(1 for item in items if item["sentiment"] == "positive")
        negatives = sum(1 for item in items if item["sentiment"] == "negative")
        high_volume = sum(1 for item in items if item["volume_signal"] == "high_volume")
        return (
            f"Snapshot context covers {len(items)} symbols: "
            f"{positives} positive, {negatives} negative, {high_volume} high-volume signals."
        )
