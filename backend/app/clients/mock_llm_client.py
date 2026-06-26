class MockLLMClient:
    """Public-safe LLM mock. It returns deterministic fake decisions."""

    def create_decision(self, candidates: list[dict]) -> dict:
        if not candidates:
            return {
                "symbol": None,
                "action": "HOLD",
                "confidence": 0,
                "recommended_order_amount": 0,
                "thesis": "No candidate passed the public demo pre-filter.",
                "risk_notes": "No LLM call was made.",
                "time_horizon": "short_term",
                "should_execute": False,
            }

        candidate = candidates[0]
        return {
            "symbol": candidate["symbol"],
            "action": "HOLD",
            "confidence": 0.62,
            "recommended_order_amount": 0,
            "thesis": "Public demo mock response prefers HOLD until real research data is connected.",
            "risk_notes": "Mock mode uses fictional data and never places real orders.",
            "time_horizon": "short_term",
            "should_execute": False,
        }
