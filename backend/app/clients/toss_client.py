import json
import time
from urllib import error, parse, request

from app.config import Settings, get_settings
from app.models import OrderStatus


_READ_CACHE: dict[tuple[str, bool, str], tuple[float, dict]] = {}


class TossClient:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    def get_status(self) -> dict:
        has_app_key = bool(self.settings.toss_app_key)
        has_app_secret = bool(self.settings.toss_app_secret)
        has_account_id = bool(self.settings.toss_account_id)
        api_credentials_ready = has_app_key and has_app_secret
        credentials_ready = api_credentials_ready and has_account_id
        account_lookup_ready = bool(
            not self.settings.use_mock_data
            and api_credentials_ready
            and self.settings.toss_token_path
            and self.settings.toss_accounts_path
        )
        live_ready = (
            credentials_ready
            and not self.settings.dry_run
            and self.settings.live_trading_enabled
            and not self.settings.use_mock_data
        )
        openai_configured = bool(self.settings.openai_api_key)
        return {
            "broker_provider": self.settings.broker_provider,
            "use_mock_data": self.settings.use_mock_data,
            "dry_run": self.settings.dry_run,
            "live_trading_enabled": self.settings.live_trading_enabled,
            "has_app_key": has_app_key,
            "has_app_secret": has_app_secret,
            "has_account_id": has_account_id,
            "api_credentials_ready": api_credentials_ready,
            "credentials_ready": credentials_ready,
            "account_lookup_ready": account_lookup_ready,
            "read_only_ready": self.settings.toss_read_only_ready,
            "openai_configured": openai_configured,
            "real_llm_ready": self.settings.real_llm_enabled,
            "live_ready": live_ready,
            "status_reason": self._status_reason(api_credentials_ready, credentials_ready, live_ready),
        }

    def place_live_order(self, *args, **kwargs):
        # Live trading must stay behind explicit configuration and safety review.
        raise NotImplementedError("Real Toss Securities order execution is not connected yet.")

    def get_accounts(self) -> dict:
        if not self._read_only_endpoint_ready(self.settings.toss_accounts_path, require_account=False):
            return self._todo_read_only_response("Toss read-only account endpoint is not configured.")
        return self._authenticated_get(self.settings.toss_accounts_path, include_account_header=False)

    def get_positions(self) -> dict:
        if not self._read_only_endpoint_ready(self.settings.toss_positions_path):
            return self._todo_read_only_response("Toss read-only positions endpoint is not configured.")
        return self._authenticated_get(self.settings.toss_positions_path)

    def preview_live_order(self, *args, **kwargs) -> dict:
        return {
            "status": OrderStatus.TODO_LIVE_ORDER_NOT_IMPLEMENTED.value,
            "message": "Live Toss Securities order preview is not connected yet.",
        }

    def cancel_live_order(self, *args, **kwargs) -> dict:
        return {
            "status": OrderStatus.TODO_LIVE_ORDER_NOT_IMPLEMENTED.value,
            "message": "Live Toss Securities order cancellation is not connected yet.",
        }

    def get_live_order_status(self, *args, **kwargs) -> dict:
        return {
            "status": OrderStatus.TODO_LIVE_ORDER_NOT_IMPLEMENTED.value,
            "message": "Live Toss Securities order status lookup is not connected yet.",
        }

    def _authenticated_get(self, path: str | None, include_account_header: bool = True) -> dict:
        if not path:
            return self._todo_read_only_response("Toss read-only endpoint path is not configured.")

        cache_key = self._cache_key(path, include_account_header)
        cached_response = self._cached_response(cache_key)
        if cached_response:
            return cached_response

        token_result = self._issue_access_token()
        if not token_result["success"]:
            return token_result

        url = self._url(path)
        headers = {
            "Authorization": f"Bearer {token_result['access_token']}",
            "Content-Type": "application/json",
        }
        if include_account_header:
            headers["X-Tossinvest-Account"] = self.settings.toss_account_id or ""

        req = request.Request(url, headers=headers, method="GET")
        try:
            with request.urlopen(req, timeout=self.settings.toss_timeout_seconds) as response:
                body = json.loads(response.read().decode("utf-8"))
            response_payload = {
                "success": True,
                "status": "OK",
                "data": body,
                "raw_response_saved": False,
            }
            self._store_cached_response(cache_key, response_payload)
            return response_payload
        except (error.HTTPError, error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            return self._safe_error_response(exc)

    def _cache_key(self, path: str, include_account_header: bool) -> tuple[str, bool, str]:
        account_id = self.settings.toss_account_id or ""
        return (path, include_account_header, account_id)

    def _cached_response(self, cache_key: tuple[str, bool, str]) -> dict | None:
        ttl_seconds = self.settings.toss_read_cache_ttl_seconds
        if ttl_seconds <= 0:
            return None

        cached = _READ_CACHE.get(cache_key)
        if not cached:
            return None

        cached_at, payload = cached
        if time.monotonic() - cached_at > ttl_seconds:
            _READ_CACHE.pop(cache_key, None)
            return None

        return {
            **payload,
            "cache_hit": True,
        }

    def _store_cached_response(self, cache_key: tuple[str, bool, str], payload: dict) -> None:
        ttl_seconds = self.settings.toss_read_cache_ttl_seconds
        if ttl_seconds <= 0 or not payload.get("success"):
            return

        _READ_CACHE[cache_key] = (time.monotonic(), payload)

    def _issue_access_token(self) -> dict:
        if not self.settings.toss_token_path:
            return self._todo_read_only_response("Toss token endpoint path is not configured.")
        if not self.settings.toss_app_key or not self.settings.toss_app_secret:
            return self._todo_read_only_response("Toss API credentials are incomplete.")

        payload = parse.urlencode(
            {
                "grant_type": "client_credentials",
                "client_id": self.settings.toss_app_key,
                "client_secret": self.settings.toss_app_secret,
            }
        ).encode("utf-8")
        req = request.Request(
            self._url(self.settings.toss_token_path),
            data=payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=self.settings.toss_timeout_seconds) as response:
                body = json.loads(response.read().decode("utf-8"))
            access_token = body.get("access_token")
            if not access_token:
                return {
                    "success": False,
                    "status": "FAILED",
                    "message": "Toss token response did not include access_token.",
                    "raw_response_saved": False,
                }
            return {
                "success": True,
                "status": "OK",
                "access_token": access_token,
                "raw_response_saved": False,
            }
        except (error.HTTPError, error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            return self._safe_error_response(exc)

    def _url(self, path: str) -> str:
        base = self.settings.toss_base_url.rstrip("/")
        normalized_path = path if path.startswith("/") else f"/{path}"
        return f"{base}{normalized_path}"

    def _read_only_endpoint_ready(self, path: str | None, require_account: bool = True) -> bool:
        return bool(
            not self.settings.use_mock_data
            and self.settings.toss_api_credentials_ready
            and (self.settings.toss_account_id or not require_account)
            and self.settings.toss_token_path
            and path
        )

    @staticmethod
    def _todo_read_only_response(message: str) -> dict:
        return {
            "success": False,
            "status": "TODO_READ_ONLY_API_NOT_CONFIGURED",
            "message": message,
            "raw_response_saved": False,
        }

    @staticmethod
    def _safe_error_response(exc: Exception) -> dict:
        http_status_code = exc.code if isinstance(exc, error.HTTPError) else None
        return {
            "success": False,
            "status": "FAILED",
            "http_status_code": http_status_code,
            "message": str(exc).replace("\n", " ")[:500],
            "raw_response_saved": False,
        }

    def _status_reason(self, api_credentials_ready: bool, credentials_ready: bool, live_ready: bool) -> str:
        if live_ready:
            return "Toss credentials are configured and live trading flags are enabled."
        if self.settings.use_mock_data:
            return "Mock data mode is enabled."
        if not api_credentials_ready:
            return "Toss API key and secret are incomplete."
        if not credentials_ready:
            return "Toss API credentials are configured, but TOSS_ACCOUNT_ID is missing."
        if self.settings.dry_run:
            return "DRY_RUN is enabled."
        if not self.settings.live_trading_enabled:
            return "LIVE_TRADING_ENABLED is false."
        return "Live trading is not ready."
