from dataclasses import dataclass
from typing import Any


@dataclass
class LLMCallResult:
    parsed_response: dict[str, Any]
    raw_response: dict[str, Any]
    usage: dict[str, Any]
    latency_ms: int
    success: bool
    error_message: str | None = None


class LLMClient:
    def create_decision(self, candidates: list[dict]) -> LLMCallResult:
        raise NotImplementedError("Real LLM calls are not connected yet.")


def estimate_usage_from_payload(
    prompt_payload: Any,
    response_payload: Any,
) -> dict[str, Any]:
    prompt_tokens = max(1, len(str(prompt_payload)) // 4)
    completion_tokens = max(1, len(str(response_payload)) // 4)
    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
        "estimated": True,
    }
