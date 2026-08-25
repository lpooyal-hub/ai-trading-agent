from dataclasses import dataclass
from typing import Any

from app.models import AgentAction


@dataclass
class GuardedDecisionResponse:
    response: dict[str, Any]
    warnings: list[str]

    @property
    def has_warnings(self) -> bool:
        return bool(self.warnings)


class DecisionResponseGuard:
    """Normalize LLM decision JSON before it becomes an AgentDecision."""

    def __init__(self, *, max_order_amount_krw: float):
        self.max_order_amount_krw = max_order_amount_krw if max_order_amount_krw > 0 else None

    def normalize(self, response: dict[str, Any], candidates: list[dict]) -> GuardedDecisionResponse:
        warnings: list[str] = []
        candidate_symbols = [str(item.get("symbol", "")).upper() for item in candidates if item.get("symbol")]
        fallback_symbol = candidate_symbols[0] if candidate_symbols else "NONE"

        symbol = str(response.get("symbol") or "").upper()
        if symbol not in candidate_symbols:
            warnings.append(f"LLM returned symbol outside candidate set: {symbol or 'EMPTY'}.")
            symbol = fallback_symbol

        action = str(response.get("action") or AgentAction.HOLD.value).upper()
        if action not in {item.value for item in AgentAction}:
            warnings.append(f"LLM returned unsupported action: {action}.")
            action = AgentAction.HOLD.value

        confidence = self._clamp_float(response.get("confidence"), 0, 1, "confidence", warnings)
        recommended_order_amount = self._clamp_float(
            response.get("recommended_order_amount"),
            0,
            self.max_order_amount_krw,
            "recommended_order_amount",
            warnings,
        )

        thesis = self._non_empty_text(
            response.get("thesis"),
            "LLM response did not include a usable thesis.",
            "thesis",
            warnings,
        )
        risk_notes = self._non_empty_text(
            response.get("risk_notes"),
            "LLM response did not include usable risk notes.",
            "risk_notes",
            warnings,
        )

        should_execute = response.get("should_execute")
        if not isinstance(should_execute, bool):
            warnings.append("LLM returned non-boolean should_execute.")
            should_execute = False
        if warnings:
            should_execute = False
            action = AgentAction.HOLD.value
            recommended_order_amount = 0

        normalized = {
            **response,
            "symbol": symbol,
            "action": action,
            "confidence": confidence,
            "recommended_order_amount": recommended_order_amount,
            "thesis": thesis,
            "risk_notes": risk_notes,
            "time_horizon": str(response.get("time_horizon") or "short_term"),
            "should_execute": should_execute,
        }
        return GuardedDecisionResponse(response=normalized, warnings=warnings)

    @staticmethod
    def _clamp_float(
        value: Any,
        minimum: float,
        maximum: float | None,
        field_name: str,
        warnings: list[str],
    ) -> float:
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            warnings.append(f"LLM returned non-numeric {field_name}.")
            return minimum

        clamped = max(parsed, minimum)
        if maximum is not None:
            clamped = min(clamped, maximum)
        if clamped != parsed:
            warnings.append(f"LLM returned out-of-range {field_name}: {parsed}.")
        return clamped

    @staticmethod
    def _non_empty_text(value: Any, fallback: str, field_name: str, warnings: list[str]) -> str:
        text = str(value or "").strip()
        if not text:
            warnings.append(f"LLM returned empty {field_name}.")
            return fallback
        return text[:2000]
