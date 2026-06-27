from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.clients.mock_market_data_client import MockMarketDataClient
from app.config import Settings, get_settings
from app.models import MarketSnapshot
from app.schemas import MarketSnapshotCreate


class MarketService:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.mock_client = MockMarketDataClient()

    def refresh_top_universe_snapshots(self, db: Session) -> list[MarketSnapshot]:
        latest_snapshots = self.get_latest_universe_snapshots(db)
        if not self.settings.use_mock_data:
            return latest_snapshots

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

    def refresh_top_universe_snapshot_result(self, db: Session) -> dict:
        if not self.settings.use_mock_data:
            return {
                "created_count": 0,
                "skipped_count": 0,
                "source": "stored_market_snapshots",
                "message": "External market data refresh is not connected yet. Use manual snapshots or an external feeder.",
                "snapshots": self.get_latest_universe_snapshots(db),
            }

        snapshots = self.refresh_top_universe_snapshots(db)
        return {
            "created_count": len(snapshots),
            "skipped_count": 0,
            "source": "fictional_demo_data",
            "message": "Demo market snapshots refreshed from mock data.",
            "snapshots": snapshots,
        }

    def create_snapshots(
        self,
        db: Session,
        snapshot_payloads: list[MarketSnapshotCreate],
    ) -> tuple[list[MarketSnapshot], int]:
        allowed_symbols = set(self.settings.active_universe)
        created: list[MarketSnapshot] = []
        skipped_count = 0

        for item in snapshot_payloads:
            symbol = item.symbol.upper()
            if symbol not in allowed_symbols:
                skipped_count += 1
                continue
            if item.sector.lower() != self.settings.allowed_sector.lower():
                skipped_count += 1
                continue

            snapshot = MarketSnapshot(
                symbol=symbol,
                price=item.price,
                change_percent=item.change_percent,
                volume=item.volume,
                sector=item.sector,
                extra_json={
                    **item.extra_json,
                    "source": item.extra_json.get("source", "manual"),
                },
            )
            db.add(snapshot)
            created.append(snapshot)

        db.commit()
        for snapshot in created:
            db.refresh(snapshot)
        return created, skipped_count

    def get_latest_universe_snapshots(self, db: Session) -> list[MarketSnapshot]:
        snapshots: list[MarketSnapshot] = []
        cutoff = datetime.utcnow() - timedelta(minutes=self.settings.market_snapshot_max_age_minutes)
        for symbol in self.settings.active_universe:
            snapshot = (
                db.query(MarketSnapshot)
                .filter(MarketSnapshot.symbol == symbol)
                .filter(MarketSnapshot.created_at >= cutoff)
                .order_by(MarketSnapshot.created_at.desc())
                .first()
            )
            if snapshot:
                snapshots.append(snapshot)
        return snapshots

    def list_recent_snapshots(self, db: Session, limit: int = 50) -> list[MarketSnapshot]:
        return (
            db.query(MarketSnapshot)
            .order_by(MarketSnapshot.created_at.desc())
            .limit(limit)
            .all()
        )
