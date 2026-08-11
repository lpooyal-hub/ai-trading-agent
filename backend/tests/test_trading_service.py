import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import Settings
from app.database import Base
from app.models import AgentAction, AgentDecision, BotPosition, OrderStatus
from app.services.trading_service import TradingService


class TradingServiceTest(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        self.settings = Settings(
            _env_file=None,
            database_url="sqlite:///:memory:",
            bot_capital_limit_krw=300000,
            min_cash_reserve_krw=30000,
            fractional_trading_enabled=False,
            quantity_decimal_places=0,
        )
        self.service = TradingService(self.settings)

    def _add_decision(self, db, *, symbol="005930", action=AgentAction.BUY, amount=50000, price=50000):
        decision = AgentDecision(
            symbol=symbol,
            sector="semiconductor",
            action=action,
            confidence=0.8,
            current_price=price,
            recommended_order_amount=amount,
            thesis="test",
            risk_notes="test",
        )
        db.add(decision)
        db.commit()
        db.refresh(decision)
        return decision

    def test_simulate_buy_order_opens_a_new_position(self):
        with self.SessionLocal() as db:
            decision = self._add_decision(db, amount=50000, price=50000)

            order = self.service.simulate_buy_order(db, decision)

            self.assertEqual(order.status, OrderStatus.SIMULATED)
            self.assertEqual(order.quantity, 1)  # 50000 / 50000, whole-share rounding

            position = db.query(BotPosition).filter(BotPosition.symbol == "005930").first()
            self.assertIsNotNone(position)
            self.assertEqual(position.quantity, 1)
            self.assertEqual(position.avg_buy_price, 50000)
            self.assertEqual(position.total_invested_amount, 50000)
            self.assertEqual(position.status, "OPEN")

    def test_simulate_buy_order_averages_into_an_existing_position(self):
        with self.SessionLocal() as db:
            first = self._add_decision(db, amount=50000, price=50000)
            self.service.simulate_buy_order(db, first)

            second = self._add_decision(db, amount=60000, price=60000)
            self.service.simulate_buy_order(db, second)

            position = db.query(BotPosition).filter(BotPosition.symbol == "005930").first()
        # quantity: 1 + 1 = 2 (both round to 1 whole share at these prices)
        self.assertEqual(position.quantity, 2)
        self.assertEqual(position.total_invested_amount, 110000)
        self.assertEqual(position.avg_buy_price, 55000)

    def test_simulate_sell_order_reduces_position_and_computes_realized_amount(self):
        with self.SessionLocal() as db:
            buy_decision = self._add_decision(db, amount=100000, price=50000)
            self.service.simulate_buy_order(db, buy_decision)  # quantity 2 @ 50000 avg

            sell_decision = self._add_decision(db, action=AgentAction.SELL, amount=0, price=60000)
            # Selling more than the recommended_order_amount-derived quantity would
            # imply -- simulate_sell_order should clamp to what's actually owned.
            sell_decision.recommended_order_amount = 120000  # -> 2 shares at price 60000
            order = self.service.simulate_sell_order(db, sell_decision)

            position = db.query(BotPosition).filter(BotPosition.symbol == "005930").first()

        self.assertEqual(order.quantity, 2)
        self.assertEqual(order.order_amount, 120000)
        self.assertEqual(position.quantity, 0)
        self.assertEqual(position.status, "CLOSED")
        self.assertEqual(position.total_invested_amount, 0)

    def test_simulate_sell_order_clamps_to_owned_quantity(self):
        with self.SessionLocal() as db:
            buy_decision = self._add_decision(db, amount=50000, price=50000)
            self.service.simulate_buy_order(db, buy_decision)  # quantity 1

            sell_decision = self._add_decision(db, action=AgentAction.SELL, amount=500000, price=50000)
            order = self.service.simulate_sell_order(db, sell_decision)

            position = db.query(BotPosition).filter(BotPosition.symbol == "005930").first()

        # Decision asks to sell 10 shares worth, but only 1 is owned.
        self.assertEqual(order.quantity, 1)
        self.assertEqual(position.quantity, 0)
        self.assertEqual(position.status, "CLOSED")

    def test_simulate_sell_order_partial_sell_keeps_position_open(self):
        with self.SessionLocal() as db:
            buy_decision = self._add_decision(db, amount=150000, price=50000)  # quantity 3
            self.service.simulate_buy_order(db, buy_decision)

            sell_decision = self._add_decision(db, action=AgentAction.SELL, amount=0, price=55000)
            sell_decision.recommended_order_amount = 55000  # -> 1 share at price 55000
            self.service.simulate_sell_order(db, sell_decision)

            position = db.query(BotPosition).filter(BotPosition.symbol == "005930").first()

        self.assertEqual(position.quantity, 2)
        self.assertEqual(position.status, "OPEN")
        # cost basis for the sold share removed proportionally (avg 50000 * 1)
        self.assertEqual(position.total_invested_amount, 100000)

    def test_calculate_available_budget_subtracts_exposure_and_reserve(self):
        with self.SessionLocal() as db:
            decision = self._add_decision(db, amount=100000, price=50000)
            self.service.simulate_buy_order(db, decision)

            budget = self.service.calculate_available_budget(db)

        # 300000 - 100000 invested - 30000 reserve
        self.assertEqual(budget, 170000)

    def test_calculate_available_budget_never_goes_negative(self):
        with self.SessionLocal() as db:
            decision = self._add_decision(db, amount=290000, price=50000)
            self.service.simulate_buy_order(db, decision)

            budget = self.service.calculate_available_budget(db)

        self.assertEqual(budget, 0)

    def test_quantity_from_decision_rounds_down_to_whole_shares_when_fractional_disabled(self):
        with self.SessionLocal() as db:
            decision = self._add_decision(db, amount=99999, price=50000)
            quantity = self.service._quantity_from_decision(decision)

        self.assertEqual(quantity, 1)  # 99999 / 50000 = 1.99998 -> floors to 1

    def test_quantity_from_decision_allows_fractions_when_enabled(self):
        settings = Settings(
            _env_file=None,
            database_url="sqlite:///:memory:",
            fractional_trading_enabled=True,
            quantity_decimal_places=4,
        )
        service = TradingService(settings)
        with self.SessionLocal() as db:
            decision = self._add_decision(db, amount=75000, price=50000)
            quantity = service._quantity_from_decision(decision)

        self.assertEqual(quantity, 1.5)


class LiveStatusUpdateTest(unittest.TestCase):
    """_live_status_update() parses varied broker status vocab into OrderStatus."""

    def test_recognizes_filled_status(self):
        result = TradingService._live_status_update({"status": "FILLED", "filled_quantity": 2, "avg_price": 51000})
        self.assertEqual(result["status"], OrderStatus.LIVE_FILLED)
        self.assertEqual(result["filled_quantity"], 2)
        self.assertEqual(result["fill_price"], 51000)

    def test_recognizes_partial_status(self):
        result = TradingService._live_status_update({"orderStatus": "PARTIALLY_FILLED"})
        self.assertEqual(result["status"], OrderStatus.LIVE_PARTIAL)

    def test_recognizes_canceled_status(self):
        result = TradingService._live_status_update({"state": "CANCELLED"})
        self.assertEqual(result["status"], OrderStatus.LIVE_CANCELED)

    def test_recognizes_failed_status(self):
        result = TradingService._live_status_update({"status": "REJECTED"})
        self.assertEqual(result["status"], OrderStatus.FAILED)

    def test_unknown_status_defaults_to_submitted(self):
        result = TradingService._live_status_update({"status": "PENDING"})
        self.assertEqual(result["status"], OrderStatus.LIVE_SUBMITTED)

    def test_finds_nested_order_id(self):
        order_id = TradingService._find_first_value(
            {"data": {"broker_response": {"order": {"orderId": "abc123"}}}}, "orderId"
        )
        self.assertEqual(order_id, "abc123")


if __name__ == "__main__":
    unittest.main()
