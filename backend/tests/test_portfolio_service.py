import unittest
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import Settings
from app.database import Base
from app.models import (
    AgentAction,
    AgentDecision,
    BotPosition,
    LLMPurpose,
    LLMUsage,
    OrderSide,
    OrderStatus,
    TradeOrder,
)
from app.services.portfolio_service import PortfolioService


class PortfolioServiceTest(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        self.settings = Settings(
            _env_file=None,
            database_url="sqlite:///:memory:",
            bot_capital_limit_krw=300000,
            min_cash_reserve_krw=30000,
            usd_to_krw_display_rate=1300,
        )
        self.service = PortfolioService(self.settings)

    def _add_decision(self, db) -> int:
        decision = AgentDecision(
            symbol="005930",
            sector="semiconductor",
            action=AgentAction.BUY,
            confidence=0.8,
            current_price=50000,
            recommended_order_amount=50000,
            thesis="test",
            risk_notes="test",
        )
        db.add(decision)
        db.commit()
        db.refresh(decision)
        return decision.id

    def _add_order(self, db, decision_id, *, side, quantity, price, order_amount):
        order = TradeOrder(
            decision_id=decision_id,
            symbol="005930",
            side=side,
            quantity=quantity,
            price=price,
            order_amount=order_amount,
            status=OrderStatus.SIMULATED,
            dry_run=True,
            reason="test",
        )
        db.add(order)
        db.commit()

    def test_get_summary_computes_available_budget_in_krw(self):
        with self.SessionLocal() as db:
            db.add(
                BotPosition(
                    symbol="005930",
                    name="Samsung Electronics",
                    sector="semiconductor",
                    quantity=1,
                    avg_buy_price=50000,
                    total_invested_amount=50000,
                    current_price=55000,
                    unrealized_pnl=5000,
                    status="OPEN",
                )
            )
            db.commit()

            summary = self.service.get_summary(db)

        self.assertEqual(summary["bot_capital_limit_krw"], 300000)
        self.assertEqual(summary["invested_amount_krw"], 50000)
        self.assertEqual(summary["unrealized_pnl_krw"], 5000)
        # 300000 - 50000 invested - 30000 reserve
        self.assertEqual(summary["available_budget_krw"], 220000)

    def test_get_performance_computes_realized_pnl_in_krw(self):
        with self.SessionLocal() as db:
            decision_id = self._add_decision(db)
            self._add_order(db, decision_id, side=OrderSide.BUY, quantity=1, price=50000, order_amount=50000)
            self._add_order(db, decision_id, side=OrderSide.SELL, quantity=1, price=60000, order_amount=60000)

            performance = self.service.get_performance(db)

        self.assertEqual(performance["gross_bought_krw"], 50000)
        self.assertEqual(performance["gross_sold_krw"], 60000)
        self.assertEqual(performance["realized_pnl_krw"], 10000)
        self.assertEqual(performance["total_pnl_krw"], 10000)
        self.assertEqual(performance["winning_sell_count"], 1)

    def test_get_cost_recovery_converts_usd_llm_cost_to_krw_before_combining(self):
        with self.SessionLocal() as db:
            decision_id = self._add_decision(db)
            self._add_order(db, decision_id, side=OrderSide.BUY, quantity=1, price=50000, order_amount=50000)
            self._add_order(db, decision_id, side=OrderSide.SELL, quantity=1, price=60000, order_amount=60000)

            db.add(
                LLMUsage(
                    model="test-model",
                    purpose=LLMPurpose.DECISION,
                    symbol="005930",
                    estimated_cost_usd=1.0,
                    created_at=datetime.utcnow(),
                )
            )
            db.commit()

            cost_recovery = self.service.get_cost_recovery(db)

        # realized_pnl_krw is 10000; LLM cost is $1.00 -> 1300 KRW at the
        # configured display rate. Everything downstream must be computed in
        # KRW, never by subtracting/dividing the raw USD figure directly.
        self.assertEqual(cost_recovery["monthly_llm_cost_usd"], 1.0)
        self.assertEqual(cost_recovery["paper_realized_pnl_krw"], 10000)
        self.assertEqual(cost_recovery["net_after_llm_cost_krw"], 10000 - 1300)
        self.assertEqual(cost_recovery["realized_net_after_llm_cost_krw"], 10000 - 1300)
        self.assertAlmostEqual(cost_recovery["llm_cost_recovery_ratio"], 10000 / 1300)
        self.assertTrue(cost_recovery["llm_cost_covered"])

    def test_get_cost_recovery_handles_zero_llm_cost(self):
        with self.SessionLocal() as db:
            cost_recovery = self.service.get_cost_recovery(db)

        self.assertEqual(cost_recovery["monthly_llm_cost_usd"], 0)
        self.assertIsNone(cost_recovery["llm_cost_recovery_ratio"])
        self.assertIsNone(cost_recovery["llm_cost_covered"])


if __name__ == "__main__":
    unittest.main()
