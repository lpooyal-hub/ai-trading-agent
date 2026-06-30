from dataclasses import dataclass
import json
import time
from typing import Any
from urllib import error, request

from app.config import Settings, get_settings
from app.strategy.prompt_builder import PromptBuilder


@dataclass
class LLMCallResult:
    parsed_response: dict[str, Any]
    raw_response: dict[str, Any]
    usage: dict[str, Any]
    latency_ms: int
    success: bool
    error_message: str | None = None


class LLMClient:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.prompt_builder = PromptBuilder()
        self.model = self.settings.llm_model_decision or "unconfigured"

    def create_decision(
        self,
        candidates: list[dict],
        news_context: dict | None = None,
        memory_context: dict | None = None,
    ) -> LLMCallResult:
        if not self.settings.real_llm_enabled:
            return self._blocked_result(
                candidates,
                "Real LLM is disabled. Set USE_MOCK_DATA=false, OPENAI_API_KEY, and LLM_MODEL_DECISION.",
            )

        payload = self._build_payload(candidates, news_context, memory_context)
        started = time.perf_counter()
        try:
            req = request.Request(
                self.settings.openai_responses_url,
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Authorization": f"Bearer {self.settings.openai_api_key}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            with request.urlopen(req, timeout=self.settings.openai_timeout_seconds) as response:
                raw_response = json.loads(response.read().decode("utf-8"))
            parsed_response = self._parse_response(raw_response)
            usage = self._extract_usage(raw_response, payload, parsed_response)
            return LLMCallResult(
                parsed_response=parsed_response,
                raw_response=self._sanitize_raw_response(raw_response),
                usage=usage,
                latency_ms=self._elapsed_ms(started),
                success=True,
            )
        except (error.HTTPError, error.URLError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
            return LLMCallResult(
                parsed_response=self._fallback_hold(candidates, f"LLM call failed: {self._safe_error(exc)}"),
                raw_response={"error": self._safe_error(exc), "provider": "openai"},
                usage=estimate_usage_from_payload(payload, str(exc)),
                latency_ms=self._elapsed_ms(started),
                success=False,
                error_message=self._safe_error(exc),
            )

    def smoke_test(self) -> LLMCallResult:
        if not self.settings.real_llm_enabled:
            return self._blocked_result(
                [{"symbol": "SMOKE_TEST"}],
                "Real LLM is disabled. Set USE_MOCK_DATA=false, OPENAI_API_KEY, and LLM_MODEL_DECISION.",
            )

        payload = {
            "model": self.model,
            "input": "Reply with exactly: OK",
            "max_output_tokens": 16,
        }
        started = time.perf_counter()
        try:
            req = request.Request(
                self.settings.openai_responses_url,
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Authorization": f"Bearer {self.settings.openai_api_key}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            with request.urlopen(req, timeout=self.settings.openai_timeout_seconds) as response:
                raw_response = json.loads(response.read().decode("utf-8"))
            output_text = self._output_text(raw_response)
            usage = self._extract_usage(raw_response, payload, {"output_text": output_text})
            return LLMCallResult(
                parsed_response={"output_text": output_text, "ok": output_text.strip().upper() == "OK"},
                raw_response=self._sanitize_raw_response(raw_response),
                usage=usage,
                latency_ms=self._elapsed_ms(started),
                success=output_text.strip().upper() == "OK",
                error_message=None if output_text.strip().upper() == "OK" else "Smoke test response was not OK.",
            )
        except (error.HTTPError, error.URLError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
            return LLMCallResult(
                parsed_response={"output_text": "", "ok": False},
                raw_response={"error": self._safe_error(exc), "provider": "openai"},
                usage=estimate_usage_from_payload(payload, str(exc)),
                latency_ms=self._elapsed_ms(started),
                success=False,
                error_message=self._safe_error(exc),
            )

    def _build_payload(
        self,
        candidates: list[dict],
        news_context: dict | None = None,
        memory_context: dict | None = None,
    ) -> dict:
        return {
            "model": self.model,
            "input": self.prompt_builder.build_decision_input(
                candidates=candidates,
                news_context=news_context,
                memory_context=memory_context,
                settings_snapshot={
                    "bot_capital_limit_usd": self.settings.bot_capital_limit_usd,
                    "max_order_amount_usd": self.settings.max_order_amount_usd,
                    "allowed_sector": self.settings.allowed_sector,
                    "allowed_symbols": self.settings.allowed_symbols,
                    "dry_run": self.settings.dry_run,
                    "live_trading_enabled": self.settings.live_trading_enabled,
                },
            ),
            "text": {
                "format": self.prompt_builder.decision_json_schema(),
            },
        }

    def _parse_response(self, raw_response: dict) -> dict:
        output_text = raw_response.get("output_text")
        if output_text:
            return json.loads(output_text)

        for output in raw_response.get("output", []):
            for content in output.get("content", []):
                if content.get("type") in {"output_text", "text"} and content.get("text"):
                    return json.loads(content["text"])

        raise ValueError("OpenAI response did not contain parseable output_text.")

    def _output_text(self, raw_response: dict) -> str:
        output_text = raw_response.get("output_text")
        if output_text:
            return str(output_text)

        for output in raw_response.get("output", []):
            for content in output.get("content", []):
                if content.get("type") in {"output_text", "text"} and content.get("text"):
                    return str(content["text"])

        raise ValueError("OpenAI response did not contain output_text.")

    def _extract_usage(self, raw_response: dict, payload: dict, parsed_response: dict) -> dict:
        usage = raw_response.get("usage") or {}
        input_tokens = usage.get("input_tokens")
        output_tokens = usage.get("output_tokens")
        total_tokens = usage.get("total_tokens")
        if input_tokens is not None and output_tokens is not None:
            return {
                "prompt_tokens": int(input_tokens),
                "completion_tokens": int(output_tokens),
                "total_tokens": int(total_tokens or input_tokens + output_tokens),
                "estimated": False,
            }
        return estimate_usage_from_payload(payload, parsed_response)

    @staticmethod
    def _sanitize_raw_response(raw_response: dict) -> dict:
        return {
            "id": raw_response.get("id"),
            "model": raw_response.get("model"),
            "status": raw_response.get("status"),
            "usage": raw_response.get("usage"),
            "output_text": raw_response.get("output_text"),
        }

    @staticmethod
    def _elapsed_ms(started: float) -> int:
        return int((time.perf_counter() - started) * 1000)

    @staticmethod
    def _safe_error(exc: Exception) -> str:
        if isinstance(exc, error.HTTPError):
            try:
                body = exc.read().decode("utf-8", errors="replace")
                return f"HTTP Error {exc.code}: {body}".replace("\n", " ")[:500]
            except Exception:
                return str(exc).replace("\n", " ")[:500]
        return str(exc).replace("\n", " ")[:500]

    def _blocked_result(self, candidates: list[dict], reason: str) -> LLMCallResult:
        parsed_response = self._fallback_hold(candidates, reason)
        return LLMCallResult(
            parsed_response=parsed_response,
            raw_response={"blocked": True, "reason": reason, "provider": "openai"},
            usage=estimate_usage_from_payload(candidates, parsed_response),
            latency_ms=0,
            success=False,
            error_message=reason,
        )

    @staticmethod
    def _fallback_hold(candidates: list[dict], reason: str) -> dict:
        symbol = candidates[0]["symbol"] if candidates else "NONE"
        return {
            "symbol": symbol,
            "action": "HOLD",
            "confidence": 0,
            "recommended_order_amount": 0,
            "thesis": reason,
            "risk_notes": "No trade should execute because the LLM call was unavailable.",
            "time_horizon": "short_term",
            "should_execute": False,
        }


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
