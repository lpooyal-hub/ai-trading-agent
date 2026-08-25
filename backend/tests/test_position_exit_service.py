import unittest
from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import Settings
from app.database import Base
from app.models import AgentDecision, BotPosition, MarketSnapshot, TradeJournalEntry, TradeOrder
from app.services.position_exit_service import PositionExitService


class PositionExitServiceTest(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        self.settings = Settings(_env_file=None, database_url="sqlite:///:memory:")
        self.settings.dry_run = True
        self.settings.live_trading_enabled = False
        self.settings.use_mock_data = True
        self.settings.agent_automation_enabled = True
        self.settings.agent_automation_mode = "paper_auto"
        self.settings.position_exit_enabled = True
        self.settings.position_stop_loss_percent = 5
        self.settings.position_take_profit_percent = 8
        self.settings.position_trailing_stop_enabled = True
        self.settings.position_trailing_activation_percent = 4
        self.settings.position_trailing_distance_percent = 2.5
        self.settings.position_max_holding_trading_days = 10
        self.settings.position_exit_max_snapshot_age_seconds = 120
        self.settings.max_order_amount_krw = 1
        self.settings.max_daily_trades = 1
        self.service = PositionExitService(self.settings)
        self.now = datetime(2026, 8, 12, 6, 0)

    def _position(self, db):
        position = BotPosition(
            symbol="005930",
            name="Samsung Electronics",
            sector="semiconductor",
            quantity=2,
            avg_buy_price=100,
            total_invested_amount=200,
            current_price=100,
            status="OPEN",
            created_at=self.now - timedelta(days=1),
        )
        db.add(position)
        db.commit()
        return position

    def _snapshot(self, price, *, age_seconds=0):
        return MarketSnapshot(
            symbol="005930",
            price=price,
            change_percent=0,
            volume=1,
            sector="semiconductor",
            extra_json={"source": "test"},
            created_at=self.now - timedelta(seconds=age_seconds),
        )

    def test_stop_loss_executes_full_paper_exit_without_llm(self):
        with self.SessionLocal() as db:
            position = self._position(db)
            snapshot = self._snapshot(94)
            db.add(snapshot)
            db.commit()

            result = self.service.run(db, [snapshot], observed_at=self.now)
            db.refresh(position)
            decision = db.query(AgentDecision).one()
            order = db.query(TradeOrder).one()
            journal = db.query(TradeJournalEntry).one()

        self.assertEqual(len(result.executions), 1)
        self.assertEqual(result.executions[0].reason_code, "STOP_LOSS")
        self.assertEqual(position.status, "CLOSED")
        self.assertEqual(position.quantity, 0)
        self.assertEqual(order.quantity, 2)
        self.assertEqual(order.order_amount, 188)
        self.assertIsNone(decision.llm_model)
        self.assertEqual(decision.total_tokens, 0)
        self.assertEqual(journal.outcome_label, "RISK_EXIT_EXECUTED")

    def test_stale_snapshot_is_rejected_without_updating_valuation(self):
        with self.SessionLocal() as db:
            position = self._position(db)
            snapshot = self._snapshot(94, age_seconds=121)
            db.add(snapshot)
            db.commit()

            result = self.service.run(db, [snapshot], observed_at=self.now)
            db.refresh(position)

        self.assertEqual(result.executions, [])
        self.assertEqual(result.skipped_symbols, ["005930"])
        self.assertEqual(position.current_price, 100)

    def test_closed_position_is_not_exited_twice(self):
        with self.SessionLocal() as db:
            self._position(db)
            snapshot = self._snapshot(94)
            db.add(snapshot)
            db.commit()

            first = self.service.run(db, [snapshot], observed_at=self.now)
            second = self.service.run(db, [snapshot], observed_at=self.now)

        self.assertEqual(len(first.executions), 1)
        self.assertEqual(second.evaluated_count, 0)
        self.assertEqual(second.executions, [])

    def test_disabled_policy_still_refreshes_valuation(self):
        self.settings.position_exit_enabled = False
        with self.SessionLocal() as db:
            position = self._position(db)
            snapshot = self._snapshot(94)
            db.add(snapshot)
            db.commit()

            result = self.service.run(db, [snapshot], observed_at=self.now)
            db.refresh(position)

        self.assertFalse(result.policy_active)
        self.assertEqual(result.executions, [])
        self.assertEqual(position.current_price, 94)
        self.assertEqual(position.unrealized_pnl_percent, -6)

    def test_real_market_snapshot_requires_a_source_quote_timestamp(self):
        self.settings.use_mock_data = False
        with self.SessionLocal() as db:
            position = self._position(db)
            snapshot = self._snapshot(94)
            db.add(snapshot)
            db.commit()

            result = self.service.run(db, [snapshot], observed_at=self.now)
            db.refresh(position)

        self.assertEqual(result.executions, [])
        self.assertEqual(result.skipped_symbols, ["005930"])
        self.assertEqual(position.current_price, 100)

    def test_real_market_snapshot_accepts_a_fresh_source_quote_timestamp(self):
        self.settings.use_mock_data = False
        with self.SessionLocal() as db:
            position = self._position(db)
            snapshot = self._snapshot(94)
            snapshot.extra_json = {"source": "test", "price_timestamp": self.now.isoformat() + "Z"}
            db.add(snapshot)
            db.commit()

            result = self.service.run(db, [snapshot], observed_at=self.now)
            db.refresh(position)

        self.assertEqual(len(result.executions), 1)
        self.assertEqual(position.status, "CLOSED")


if __name__ == "__main__":
    unittest.main()
