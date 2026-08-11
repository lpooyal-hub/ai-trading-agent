import unittest
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import Settings
from app.database import Base
from app.models import AgentAction, BotPosition, LegacyPosition
from app.risk.risk_manager import RiskManager


class RiskManagerTest(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        self.settings = Settings(
            _env_file=None,
            database_url="sqlite:///:memory:",
            dry_run=True,
            live_trading_enabled=False,
            use_mock_data=True,
            allowed_symbols_csv="005930,035420",
            bot_capital_limit_krw=300000,
            max_order_amount_krw=130000,
            max_positions=3,
            max_daily_trades=5,
            max_symbol_exposure_percent=40,
            min_order_amount_krw=5000,
            fractional_trading_enabled=False,
        )
        self.manager = RiskManager(self.settings)

    def test_approves_small_buy_inside_limits(self):
        with self.SessionLocal() as db:
            result = self.manager.validate_decision(
                self._decision(symbol="005930", amount=50000, price=50000),
                db,
                available_bot_budget=270000,
            )

        self.assertTrue(result["approved"])

    def test_rejects_symbol_outside_active_universe(self):
        # Not "005380": for a validation_alias field (allowed_symbols_csv /
        # ALLOWED_SYMBOLS), the real ALLOWED_SYMBOLS env var set by
        # docker-compose's backend/.env wins over this test's constructor
        # kwarg, so the effective universe can silently be the full default
        # list rather than the two symbols passed above. Use a code that is
        # outside both to keep this test correct either way.
        with self.SessionLocal() as db:
            result = self.manager.validate_decision(
                self._decision(symbol="999999", amount=50000, price=50000),
                db,
                available_bot_budget=270000,
            )

        self.assertFalse(result["approved"])
        self.assertIn("outside the active universe", result["reason"])

    def test_rejects_protected_legacy_only_position(self):
        with self.SessionLocal() as db:
            db.add(
                LegacyPosition(
                    symbol="005930",
                    name="Samsung Electronics",
                    quantity=1,
                    avg_price=50000,
                    is_protected=True,
                )
            )
            db.commit()

            result = self.manager.validate_decision(
                self._decision(symbol="005930", amount=50000, price=50000),
                db,
                available_bot_budget=270000,
            )

        self.assertFalse(result["approved"])
        self.assertIn("protected legacy position", result["reason"])

    def test_rejects_symbol_exposure_limit(self):
        with self.SessionLocal() as db:
            db.add(
                BotPosition(
                    symbol="005930",
                    name="Samsung Electronics",
                    sector="semiconductor",
                    quantity=1,
                    avg_buy_price=90000,
                    total_invested_amount=90000,
                    current_price=100000,
                    status="OPEN",
                )
            )
            db.commit()

            result = self.manager.validate_decision(
                self._decision(symbol="005930", amount=40000, price=40000),
                db,
                available_bot_budget=180000,
            )

        self.assertFalse(result["approved"])
        self.assertIn("Symbol exposure limit", result["reason"])

    @staticmethod
    def _decision(symbol: str, amount: float, price: float):
        return SimpleNamespace(
            symbol=symbol,
            sector="semiconductor",
            action=AgentAction.BUY,
            recommended_order_amount=amount,
            current_price=price,
            name=symbol,
        )


if __name__ == "__main__":
    unittest.main()
