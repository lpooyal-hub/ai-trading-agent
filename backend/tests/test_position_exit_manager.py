import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace

from app.config import Settings
from app.risk.position_exit_manager import PositionExitManager


class PositionExitManagerTest(unittest.TestCase):
    def setUp(self):
        self.settings = Settings(_env_file=None)
        self.settings.position_stop_loss_percent = 5
        self.settings.position_take_profit_percent = 8
        self.settings.position_trailing_stop_enabled = True
        self.settings.position_trailing_activation_percent = 4
        self.settings.position_trailing_distance_percent = 2.5
        self.settings.position_max_holding_trading_days = 10
        self.manager = PositionExitManager(self.settings)
        self.now = datetime(2026, 8, 12, 6, 0)

    def _position(self, *, price=100, days_ago=1):
        return SimpleNamespace(
            symbol="005930",
            quantity=2,
            avg_buy_price=price,
            created_at=self.now - timedelta(days=days_ago),
        )

    def test_stop_loss_has_priority(self):
        signal = self.manager.evaluate(
            self._position(),
            current_price=94,
            peak_price=110,
            observed_at=self.now,
        )

        self.assertEqual(signal.reason_code, "STOP_LOSS")
        self.assertEqual(signal.pnl_percent, -6)

    def test_take_profit_exits_at_target(self):
        signal = self.manager.evaluate(
            self._position(),
            current_price=108,
            peak_price=108,
            observed_at=self.now,
        )

        self.assertEqual(signal.reason_code, "TAKE_PROFIT")

    def test_trailing_stop_protects_an_activated_gain(self):
        signal = self.manager.evaluate(
            self._position(),
            current_price=105,
            peak_price=108,
            observed_at=self.now,
        )

        self.assertEqual(signal.reason_code, "TRAILING_STOP")
        self.assertGreater(signal.drawdown_from_peak_percent, 2.5)

    def test_trailing_stop_does_not_activate_before_minimum_gain(self):
        signal = self.manager.evaluate(
            self._position(),
            current_price=99,
            peak_price=103,
            observed_at=self.now,
        )

        self.assertIsNone(signal)

    def test_max_holding_period_counts_weekdays(self):
        position = self._position(days_ago=16)
        signal = self.manager.evaluate(
            position,
            current_price=101,
            peak_price=102,
            observed_at=self.now,
        )

        self.assertEqual(signal.reason_code, "MAX_HOLDING_PERIOD")
        self.assertGreaterEqual(signal.holding_trading_days, 10)

    def test_invalid_position_data_fails_closed(self):
        position = self._position(price=0)
        signal = self.manager.evaluate(
            position,
            current_price=94,
            peak_price=100,
            observed_at=self.now,
        )

        self.assertIsNone(signal)


if __name__ == "__main__":
    unittest.main()
