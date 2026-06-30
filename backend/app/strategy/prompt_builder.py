import json


class PromptBuilder:
    def build_decision_input(
        self,
        *,
        candidates: list[dict],
        news_context: dict | None = None,
        settings_snapshot: dict,
    ) -> list[dict]:
        return [
            {
                "role": "system",
                "content": [
                    {
                        "type": "input_text",
                        "text": (
                            "You are a paper-trading research assistant. "
                            "This is not financial advice. Evaluate only the provided candidate symbols. "
                            "Prefer HOLD when confidence is low or data is insufficient. "
                            "Avoid hype-based decisions and explain risks briefly. "
                            "Return only valid JSON matching the schema."
                        ),
                    }
                ],
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": json.dumps(
                            {
                                "settings": settings_snapshot,
                                "candidates": candidates,
                                "news_context": news_context or {
                                    "summary": "No news context provided.",
                                    "items": [],
                                },
                                "required_json_shape": {
                                    "symbol": "NVDA",
                                    "action": "BUY|SELL|HOLD",
                                    "confidence": 0.0,
                                    "recommended_order_amount": 0,
                                    "thesis": "short explanation",
                                    "risk_notes": "short risk explanation",
                                    "time_horizon": "short_term",
                                    "should_execute": False,
                                },
                            },
                            ensure_ascii=True,
                        ),
                    }
                ],
            },
        ]

    def decision_json_schema(self) -> dict:
        return {
            "type": "json_schema",
            "name": "agent_decision",
            "strict": True,
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "symbol": {"type": "string"},
                    "action": {"type": "string", "enum": ["BUY", "SELL", "HOLD"]},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "recommended_order_amount": {"type": "number", "minimum": 0},
                    "thesis": {"type": "string"},
                    "risk_notes": {"type": "string"},
                    "time_horizon": {"type": "string"},
                    "should_execute": {"type": "boolean"},
                },
                "required": [
                    "symbol",
                    "action",
                    "confidence",
                    "recommended_order_amount",
                    "thesis",
                    "risk_notes",
                    "time_horizon",
                    "should_execute",
                ],
            },
        }
