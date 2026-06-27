import json
from urllib import error, parse, request

from app.config import Settings, get_settings
from app.models import OrderStatus


class TossClient:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    def get_status(self) -> dict:
        has_app_key = bool(self.settings.toss_app_key)
        has_app_secret = bool(self.settings.toss_app_secret)
        has_account_id = bool(self.settings.toss_account_id)
        credentials_ready = has_app_key and has_app_secret and has_account_id
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
            "credentials_ready": credentials_ready,
            "read_only_ready": self.settings.toss_read_only_ready,
            "openai_configured": openai_configured,
            "real_llm_ready": self.settings.real_llm_enabled,
            "live_ready": live_ready,
            "status_reason": self._status_reason(credentials_ready, live_ready),
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
            return {
                "success": True,
                "status": "OK",
                "data": body,
                "raw_response_saved": False,
            }
        except (error.HTTPError, error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            return self._safe_error_response(exc)

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
        return {
            "success": False,
            "status": "FAILED",
            "message": str(exc).replace("\n", " ")[:500],
            "raw_response_saved": False,
        }

    def _status_reason(self, credentials_ready: bool, live_ready: bool) -> str:
        if live_ready:
            return "Toss credentials are configured and live trading flags are enabled."
        if self.settings.use_mock_data:
            return "Mock data mode is enabled."
        if self.settings.dry_run:
            return "DRY_RUN is enabled."
        if not self.settings.live_trading_enabled:
            return "LIVE_TRADING_ENABLED is false."
        if not credentials_ready:
            return "Toss credentials are incomplete."
        return "Live trading is not ready."
