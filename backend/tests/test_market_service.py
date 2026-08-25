import unittest
from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import Settings
from app.database import Base
from app.models import MarketSnapshot
from app.schemas import MarketSnapshotCreate
from app.services.market_service import MarketService


class MarketServiceTest(unittest.TestCase):
    ACTIVE_UNIVERSE = ["005930", "035420"]
    OUTSIDE_UNIVERSE = "999999"

    def setUp(self):
        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        self.settings = self._settings(use_mock_data=True)
        self.service = MarketService(self.settings)

        # allowed_symbols_csv has validation_alias="ALLOWED_SYMBOLS". Passing
        # the alias itself keeps a real process environment variable from
        # silently replacing this test's intended two-symbol universe.
        self.assertEqual(self.settings.active_universe, self.ACTIVE_UNIVERSE)

    def _settings(self, *, use_mock_data: bool) -> Settings:
        return Settings(
            _env_file=None,
            database_url="sqlite:///:memory:",
            use_mock_data=use_mock_data,
            ALLOWED_SYMBOLS=",".join(self.ACTIVE_UNIVERSE),
            market_snapshot_max_age_minutes=30,
            # toss_app_key/toss_app_secret also have validation_alias, so the
            # real TOSS_API_KEY/TOSS_SECRET_KEY docker-compose injects from
            # backend/.env would otherwise leak in here too and make this
            # test hit the real Toss API. Force them off explicitly.
            TOSS_API_KEY="",
            TOSS_SECRET_KEY="",
        )

    @staticmethod
    def _snapshot(
        symbol: str,
        *,
        created_at: datetime,
        price: float = 50000,
        sector: str = "semiconductor",
    ) -> MarketSnapshot:
        return MarketSnapshot(
            symbol=symbol,
            price=price,
            change_percent=1.0,
            volume=1_000_000,
            sector=sector,
            extra_json={"source": "test"},
            created_at=created_at,
        )

    def test_get_latest_universe_snapshots_returns_latest_fresh_active_rows_only(self):
        now = datetime.utcnow()
        with self.SessionLocal() as db:
            db.add_all(
                [
                    self._snapshot("005930", created_at=now - timedelta(minutes=10), price=50000),
                    self._snapshot("005930", created_at=now - timedelta(minutes=1), price=55000),
                    self._snapshot("035420", created_at=now - timedelta(minutes=31), price=200000),
                    self._snapshot(
                        self.OUTSIDE_UNIVERSE,
                        created_at=now - timedelta(minutes=1),
                        price=10000,
                    ),
                ]
            )
            db.commit()

            snapshots = self.service.get_latest_universe_snapshots(db)

        self.assertEqual(len(snapshots), 1)
        self.assertEqual(snapshots[0].symbol, "005930")
        self.assertEqual(snapshots[0].price, 55000)

    def test_refresh_without_mock_data_returns_existing_snapshots_without_inserting(self):
        service = MarketService(self._settings(use_mock_data=False))
        with self.SessionLocal() as db:
            existing = self._snapshot("005930", created_at=datetime.utcnow())
            db.add(existing)
            db.commit()
            db.refresh(existing)
            row_count_before = db.query(MarketSnapshot).count()
            expected_ids = [
                snapshot.id for snapshot in service.get_latest_universe_snapshots(db)
            ]

            snapshots = service.refresh_active_universe_snapshots(db)

            self.assertEqual(db.query(MarketSnapshot).count(), row_count_before)
            returned_ids = [snapshot.id for snapshot in snapshots]

        self.assertEqual(returned_ids, expected_ids)

    def test_refresh_with_mock_data_persists_and_returns_active_universe_snapshots(self):
        with self.SessionLocal() as db:
            snapshots = self.service.refresh_active_universe_snapshots(db)
            persisted = db.query(MarketSnapshot).all()

        active_symbols = set(self.settings.active_universe)
        self.assertEqual(len(snapshots), len(active_symbols))
        self.assertEqual(len(persisted), len(active_symbols))
        self.assertEqual({snapshot.symbol for snapshot in snapshots}, active_symbols)
        self.assertTrue(all(snapshot.symbol in active_symbols for snapshot in snapshots))
        self.assertTrue(all(snapshot.symbol in active_symbols for snapshot in persisted))
        self.assertTrue(all(snapshot.id is not None for snapshot in snapshots))

    def test_refresh_includes_explicit_held_symbol_outside_entry_universe(self):
        with self.SessionLocal() as db:
            snapshots = self.service.refresh_active_universe_snapshots(
                db,
                extra_symbols=[self.OUTSIDE_UNIVERSE],
            )

        symbols = {snapshot.symbol for snapshot in snapshots}
        self.assertEqual(symbols, {*self.ACTIVE_UNIVERSE, self.OUTSIDE_UNIVERSE})

    def test_get_snapshot_status_is_not_ready_when_no_fresh_snapshots_exist(self):
        with self.SessionLocal() as db:
            status = self.service.get_snapshot_status(db)

        self.assertFalse(status["ready_for_agent"])
        self.assertEqual(status["fresh_symbol_count"], 0)
        self.assertEqual(status["missing_symbol_count"], len(self.ACTIVE_UNIVERSE))
        self.assertTrue(status["message"].startswith("No fresh market snapshots"))

    def test_get_snapshot_status_reports_exact_missing_count_for_partial_universe(self):
        with self.SessionLocal() as db:
            db.add(self._snapshot("005930", created_at=datetime.utcnow()))
            db.commit()

            status = self.service.get_snapshot_status(db)

        self.assertFalse(status["ready_for_agent"])
        self.assertEqual(status["fresh_symbol_count"], 1)
        self.assertEqual(status["missing_symbol_count"], 1)
        self.assertEqual(status["missing_symbols"], ["035420"])
        self.assertIn("1 symbols are missing", status["message"])

    def test_get_snapshot_status_is_ready_when_entire_universe_is_fresh(self):
        now = datetime.utcnow()
        with self.SessionLocal() as db:
            db.add_all(
                [
                    self._snapshot("005930", created_at=now),
                    self._snapshot("035420", created_at=now, sector="internet"),
                ]
            )
            db.commit()

            status = self.service.get_snapshot_status(db)

        self.assertTrue(status["ready_for_agent"])
        self.assertEqual(status["fresh_symbol_count"], len(self.ACTIVE_UNIVERSE))
        self.assertEqual(status["missing_symbol_count"], 0)
        self.assertEqual(status["missing_symbols"], [])

    def test_create_snapshots_creates_active_symbols_and_skips_outside_symbols(self):
        payloads = [
            MarketSnapshotCreate(
                symbol="005930",
                price=60000,
                change_percent=1.2,
                volume=2_000_000,
                sector="semiconductor",
            ),
            MarketSnapshotCreate(
                symbol=self.OUTSIDE_UNIVERSE,
                price=10000,
                change_percent=-0.5,
                volume=100_000,
                sector="unknown",
            ),
        ]

        with self.SessionLocal() as db:
            created, skipped_count = self.service.create_snapshots(db, payloads)
            persisted_symbols = {
                snapshot.symbol for snapshot in db.query(MarketSnapshot).all()
            }

        self.assertEqual([snapshot.symbol for snapshot in created], ["005930"])
        self.assertEqual(skipped_count, 1)
        self.assertEqual(persisted_symbols, {"005930"})
        self.assertNotIn(self.OUTSIDE_UNIVERSE, persisted_symbols)

    def test_list_recent_snapshots_orders_descending_and_applies_limit(self):
        now = datetime.utcnow()
        with self.SessionLocal() as db:
            db.add_all(
                [
                    self._snapshot(
                        "005930",
                        created_at=now - timedelta(minutes=minutes_ago),
                        price=50000 + minutes_ago,
                    )
                    for minutes_ago in range(5)
                ]
            )
            db.commit()

            snapshots = self.service.list_recent_snapshots(db, limit=2)

        self.assertEqual(len(snapshots), 2)
        self.assertGreater(snapshots[0].created_at, snapshots[1].created_at)
        self.assertEqual(
            [snapshot.created_at for snapshot in snapshots],
            [now, now - timedelta(minutes=1)],
        )


if __name__ == "__main__":
    unittest.main()
