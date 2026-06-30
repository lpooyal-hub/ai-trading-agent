from app.clients.llm_client import LLMCallResult, estimate_usage_from_payload


class MockLLMClient:
    """Public-safe LLM mock. It returns deterministic fake decisions."""

    model = "mock-llm"

    def create_decision(self, candidates: list[dict], news_context: dict | None = None) -> LLMCallResult:
        if not candidates:
            parsed_response = {
                "symbol": None,
                "action": "HOLD",
                "confidence": 0,
                "recommended_order_amount": 0,
                "thesis": "No candidate passed the public demo pre-filter.",
                "risk_notes": "No LLM call was made.",
                "time_horizon": "short_term",
                "should_execute": False,
            }
            return self._result(candidates, parsed_response, news_context)

        candidate = candidates[0]
        parsed_response = {
            "symbol": candidate["symbol"],
            "action": "BUY",
            "confidence": 0.68,
            "recommended_order_amount": 50,
            "thesis": "Public demo mock response suggests a small paper-trade position for review.",
            "risk_notes": "Mock mode uses fictional data, requires RiskManager approval, and never places real orders.",
            "time_horizon": "short_term",
            "should_execute": True,
        }
        return self._result(candidates, parsed_response, news_context)

    def _result(self, candidates: list[dict], parsed_response: dict, news_context: dict | None) -> LLMCallResult:
        usage = estimate_usage_from_payload({"candidates": candidates, "news_context": news_context}, parsed_response)
        return LLMCallResult(
            parsed_response=parsed_response,
            raw_response={
                "provider": "mock",
                "model": self.model,
                "response": parsed_response,
                "news_context": news_context or {},
            },
            usage=usage,
            latency_ms=10,
            success=True,
        )
