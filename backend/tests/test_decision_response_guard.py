import unittest

from app.models import AgentAction
from app.strategy.decision_response_guard import DecisionResponseGuard


class DecisionResponseGuardTest(unittest.TestCase):
    def test_valid_response_passes_without_warnings(self):
        guard = DecisionResponseGuard(max_order_amount_krw=130000)

        result = guard.normalize(
            {
                "symbol": "NVDA",
                "action": "BUY",
                "confidence": 0.82,
                "recommended_order_amount": 50000,
                "thesis": "Momentum is improving.",
                "risk_notes": "Position size is limited.",
                "should_execute": True,
            },
            candidates=[{"symbol": "NVDA"}],
        )

        self.assertFalse(result.has_warnings)
        self.assertEqual(result.response["symbol"], "NVDA")
        self.assertEqual(result.response["action"], AgentAction.BUY.value)
        self.assertTrue(result.response["should_execute"])

    def test_invalid_response_is_normalized_to_safe_hold(self):
        guard = DecisionResponseGuard(max_order_amount_krw=130000)

        result = guard.normalize(
            {
                "symbol": "OUTSIDE",
                "action": "JUMP",
                "confidence": 2,
                "recommended_order_amount": 500000,
                "thesis": "",
                "risk_notes": "",
                "should_execute": "yes",
            },
            candidates=[{"symbol": "AMD"}],
        )

        self.assertTrue(result.has_warnings)
        self.assertEqual(result.response["symbol"], "AMD")
        self.assertEqual(result.response["action"], AgentAction.HOLD.value)
        self.assertEqual(result.response["recommended_order_amount"], 0)
        self.assertFalse(result.response["should_execute"])


if __name__ == "__main__":
    unittest.main()
