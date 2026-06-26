from sqlalchemy.orm import Session

from app.clients.mock_market_data_client import MockMarketDataClient
from app.config import Settings, get_settings
from app.models import MarketSnapshot


class MarketService:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.mock_client = MockMarketDataClient()

    def refresh_top_universe_snapshots(self, db: Session) -> list[MarketSnapshot]:
        raw_snapshots = self.mock_client.get_semiconductor_snapshots()
        allowed_symbols = set(self.settings.active_universe)
        snapshots: list[MarketSnapshot] = []

        for item in raw_snapshots:
            symbol = item["symbol"].upper()
            if symbol not in allowed_symbols:
                continue

            snapshot = MarketSnapshot(
                symbol=symbol,
                price=item["price"],
                change_percent=item["change_percent"],
                volume=item["volume"],
                sector=item["sector"],
                extra_json=item.get("extra_json", {}),
            )
            db.add(snapshot)
            snapshots.append(snapshot)

        db.commit()
        for snapshot in snapshots:
            db.refresh(snapshot)

        return snapshots
