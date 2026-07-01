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
            allowed_symbols_csv="NVDA,AMD",
            allowed_sector="semiconductor",
            bot_capital_limit_usd=250,
            max_order_amount_usd=100,
            max_positions=3,
            max_daily_trades=5,
            max_symbol_exposure_percent=40,
            min_order_amount_usd=5,
            fractional_trading_enabled=True,
        )
        self.manager = RiskManager(self.settings)

    def test_approves_small_buy_inside_limits(self):
        with self.SessionLocal() as db:
            result = self.manager.validate_decision(
                self._decision(symbol="NVDA", amount=50, price=100),
                db,
                available_bot_budget=250,
            )

        self.assertTrue(result["approved"])

    def test_rejects_symbol_outside_active_universe(self):
        with self.SessionLocal() as db:
            result = self.manager.validate_decision(
                self._decision(symbol="TSLA", amount=50, price=100),
                db,
                available_bot_budget=250,
            )

        self.assertFalse(result["approved"])
        self.assertIn("outside the active universe", result["reason"])

    def test_rejects_protected_legacy_only_position(self):
        with self.SessionLocal() as db:
            db.add(
                LegacyPosition(
                    symbol="NVDA",
                    name="NVIDIA",
                    quantity=1,
                    avg_price=100,
                    is_protected=True,
                )
            )
            db.commit()

            result = self.manager.validate_decision(
                self._decision(symbol="NVDA", amount=50, price=100),
                db,
                available_bot_budget=250,
            )

        self.assertFalse(result["approved"])
        self.assertIn("protected legacy position", result["reason"])

    def test_rejects_symbol_exposure_limit(self):
        with self.SessionLocal() as db:
            db.add(
                BotPosition(
                    symbol="NVDA",
                    name="NVIDIA",
                    sector="semiconductor",
                    quantity=1,
                    avg_buy_price=90,
                    total_invested_amount=90,
                    current_price=100,
                    status="OPEN",
                )
            )
            db.commit()

            result = self.manager.validate_decision(
                self._decision(symbol="NVDA", amount=20, price=100),
                db,
                available_bot_budget=160,
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
