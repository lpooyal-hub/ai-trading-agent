from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.clients.market_data_client import MarketDataClient
from app.clients.mock_market_data_client import MockMarketDataClient
from app.config import Settings, get_settings
from app.models import MarketSnapshot
from app.schemas import MarketSnapshotCreate


class MarketService:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.mock_client = MockMarketDataClient()
        # Pass settings through explicitly -- previously this constructed
        # MarketDataClient() with no settings, so it silently used the
        # process-wide get_settings() instead of this MarketService's
        # settings (harmless while MarketDataClient was a no-op placeholder,
        # but wrong now that it makes real Toss API calls, and it broke test
        # isolation for anyone constructing MarketService(custom_settings)).
        self.market_data_client = MarketDataClient(self.settings)

    def refresh_active_universe_snapshots(self, db: Session) -> list[MarketSnapshot]:
        return self.refresh_active_universe_snapshot_result(db)["snapshots"]

    def refresh_active_universe_snapshot_result(self, db: Session) -> dict:
        if self.settings.use_mock_data:
            return self._refresh_mock_snapshot_result(db)
        return self._refresh_real_snapshot_result(db)

    def _refresh_mock_snapshot_result(self, db: Session) -> dict:
        raw_snapshots = self.mock_client.get_demo_snapshots(symbols=self.settings.active_universe)
        snapshots = self._persist_snapshots(db, raw_snapshots)
        return {
            "created_count": len(snapshots),
            "skipped_count": 0,
            "source": "fictional_demo_data",
            "message": "Demo market snapshots refreshed from mock data.",
            "snapshots": snapshots,
        }

    def _refresh_real_snapshot_result(self, db: Session) -> dict:
        fetch_result = self.market_data_client.get_market_snapshots(self.settings.active_universe)
        if fetch_result.success and fetch_result.snapshots:
            snapshots = self._persist_snapshots(db, fetch_result.snapshots)
            return {
                "created_count": len(snapshots),
                "skipped_count": max(len(fetch_result.snapshots) - len(snapshots), 0),
                "source": self.market_data_client.provider_name,
                "message": fetch_result.message,
                "snapshots": snapshots,
            }
        # Fetch failed, wasn't configured, or returned nothing usable --
        # fall back to whatever is still within the freshness window
        # (get_latest_universe_snapshots) rather than going completely
        # blind for one bad cycle.
        return {
            "created_count": 0,
            "skipped_count": 0,
            "source": self.market_data_client.provider_name,
            "message": fetch_result.message,
            "snapshots": self.get_latest_universe_snapshots(db),
        }

    def _persist_snapshots(self, db: Session, raw_snapshots: list[dict]) -> list[MarketSnapshot]:
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

    def get_snapshot_status(self, db: Session) -> dict:
        latest_snapshots = self.get_latest_universe_snapshots(db)
        fresh_symbols = {snapshot.symbol for snapshot in latest_snapshots}
        active_universe = self.settings.active_universe
        missing_symbols = [symbol for symbol in active_universe if symbol not in fresh_symbols]
        ready_for_agent = bool(active_universe) and not missing_symbols
        if ready_for_agent:
            message = "Fresh market snapshots are available for every active universe symbol."
        elif latest_snapshots:
            message = f"{len(latest_snapshots)} fresh market snapshots are available, but {len(missing_symbols)} symbols are missing."
        else:
            message = "No fresh market snapshots are available for agent input."
        return {
            "active_universe": active_universe,
            "fresh_symbol_count": len(latest_snapshots),
            "missing_symbol_count": len(missing_symbols),
            "missing_symbols": missing_symbols,
            "max_age_minutes": self.settings.market_snapshot_max_age_minutes,
            "ready_for_agent": ready_for_agent,
            "message": message,
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
