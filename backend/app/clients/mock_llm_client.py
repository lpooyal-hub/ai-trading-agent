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
            "action": "BUY",
            "confidence": 0.68,
            "recommended_order_amount": 50,
            "thesis": "Public demo mock response suggests a small paper-trade position for review.",
            "risk_notes": "Mock mode uses fictional data, requires RiskManager approval, and never places real orders.",
            "time_horizon": "short_term",
            "should_execute": True,
        }
