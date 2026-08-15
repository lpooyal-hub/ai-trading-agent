import json


class PromptBuilder:
    decision_prompt_version = "decision-v3-balanced-paper-entry"
    decision_strategy_name = "bounded-intraday-paper-trading"

    def decision_metadata(self) -> dict:
        return {
            "version": self.decision_prompt_version,
            "strategy_name": self.decision_strategy_name,
            "schema_name": "agent_decision",
        }

    def build_decision_input(
        self,
        *,
        candidates: list[dict],
        news_context: dict | None = None,
        memory_context: dict | None = None,
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
                            "Treat intraday_signal as an event trigger and market context, not as a BUY/SELL instruction. "
                            "The goal is to produce useful, bounded paper-trading evidence, not to minimize all activity. "
                            "Choose BUY only when fresh 5m and 15m momentum is positive and directionally consistent, "
                            "the spread is acceptable, and news does not show a material near-term risk. "
                            "Do not reject an otherwise valid small paper entry solely because the daily change is already large. "
                            "Choose HOLD when momentum is negative or mixed, evidence is stale or insufficient, or risk is material. "
                            "For BUY, recommend at least one whole-share price and generally 10-20% of paper capital, "
                            "without exceeding the provided order or symbol exposure limits. "
                            "Use calibrated confidence; should_execute may be true only for BUY with confidence at or above "
                            "the paper auto-execution threshold. "
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
                                "prompt_metadata": self.decision_metadata(),
                                "settings": settings_snapshot,
                                "candidates": candidates,
                                "news_context": news_context or {
                                    "summary": "No news context provided.",
                                    "items": [],
                                },
                                "memory_context": memory_context or {
                                    "summary": "No memory context provided.",
                                    "recent_lessons": [],
                                    "common_mistakes": [],
                                },
                                "required_json_shape": {
                                    "symbol": "005930",
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
