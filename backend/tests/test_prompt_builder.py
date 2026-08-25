import unittest

from app.strategy.prompt_builder import PromptBuilder


class PromptBuilderTest(unittest.TestCase):
    def test_decision_prompt_balances_paper_entries_and_hold_guards(self):
        builder = PromptBuilder()

        prompt = builder.build_decision_input(
            candidates=[],
            settings_snapshot={},
        )[0]["content"][0]["text"]

        self.assertEqual(builder.decision_prompt_version, "decision-v3-balanced-paper-entry")
        self.assertIn("produce useful, bounded paper-trading evidence", prompt)
        self.assertIn("Choose BUY only when fresh 5m and 15m momentum is positive", prompt)
        self.assertIn("Choose HOLD when momentum is negative or mixed", prompt)
        self.assertNotIn("Prefer HOLD", prompt)


if __name__ == "__main__":
    unittest.main()
