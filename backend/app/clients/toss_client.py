import json
import time
from urllib import error, parse, request

from app.config import Settings, get_settings
from app.models import OrderStatus


_READ_CACHE: dict[tuple[str, bool, str], tuple[float, dict]] = {}


class TossClient:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self._access_token: str | None = None
        self._access_token_expires_at = 0.0

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
        order_intent = kwargs.get("order_intent") if kwargs else None
        if not order_intent and args:
            order_intent = args[0]
        if not isinstance(order_intent, dict):
            return self._live_order_error_response("Live order intent is required.")
        if not self._live_order_endpoint_ready():
            return self._live_order_error_response("Toss live order endpoint or credentials are not configured.")
        return self._authenticated_post(
            self.settings.toss_order_path,
            self._live_order_payload(order_intent),
            idempotency_key=order_intent.get("idempotency_key"),
        )

    def get_accounts(self) -> dict:
        if not self._read_only_endpoint_ready(self.settings.toss_accounts_path, require_account=False):
            return self._todo_read_only_response("Toss read-only account endpoint is not configured.")
        return self._authenticated_get(self.settings.toss_accounts_path, include_account_header=False)

    def get_positions(self) -> dict:
        if not self._read_only_endpoint_ready(self.settings.toss_positions_path):
            return self._todo_read_only_response("Toss read-only positions endpoint is not configured.")
        return self._authenticated_get(self.settings.toss_positions_path)

    def get_daily_candles(self, symbol: str, count: int = 2) -> dict:
        """Latest daily candles (open/high/low/close/volume) for one symbol.
        Account-independent (public market data), so require_account=False.
        Used to derive price/change_percent/volume for MarketDataClient,
        since Toss's current-price endpoint doesn't include those."""
        if not self._read_only_endpoint_ready(self.settings.toss_candles_path, require_account=False):
            return self._todo_read_only_response("Toss candles endpoint is not configured.")
        path = (
            f"{self.settings.toss_candles_path}"
            f"?symbol={parse.quote(symbol)}&interval=1d&count={count}"
        )
        return self._authenticated_get(path, include_account_header=False)

    def get_current_prices(self, symbols: list[str]) -> dict:
        """Fetch up to 200 current prices in one account-independent call."""
        if not self._read_only_endpoint_ready(self.settings.toss_prices_path, require_account=False):
            return self._todo_read_only_response("Toss current-prices endpoint is not configured.")
        normalized = [symbol.strip().upper() for symbol in symbols if symbol.strip()][:200]
        if not normalized:
            return {
                "success": True,
                "status": "OK",
                "data": {"result": []},
                "raw_response_saved": False,
            }
        query = parse.urlencode({"symbols": ",".join(normalized)})
        return self._authenticated_get(
            f"{self.settings.toss_prices_path}?{query}",
            include_account_header=False,
        )

    def get_intraday_candles(self, symbol: str, count: int = 30) -> dict:
        """Latest 1-minute candles for deterministic intraday signal calculation."""
        if not self._read_only_endpoint_ready(self.settings.toss_candles_path, require_account=False):
            return self._todo_read_only_response("Toss candles endpoint is not configured.")
        safe_count = min(max(int(count), 1), 200)
        path = (
            f"{self.settings.toss_candles_path}"
            f"?symbol={parse.quote(symbol)}&interval=1m&count={safe_count}"
        )
        return self._authenticated_get(path, include_account_header=False)

    def get_orderbook(self, symbol: str) -> dict:
        """Latest bid/ask levels for spread validation."""
        if not self._read_only_endpoint_ready(self.settings.toss_orderbook_path, require_account=False):
            return self._todo_read_only_response("Toss orderbook endpoint is not configured.")
        path = f"{self.settings.toss_orderbook_path}?symbol={parse.quote(symbol)}"
        return self._authenticated_get(path, include_account_header=False)

    def preview_live_order(self, *args, **kwargs) -> dict:
        return self._todo_live_order_response(
            "Live Toss Securities order preview is not a broker-side preview call; use internal decision preview."
        )

    def cancel_live_order(self, *args, **kwargs) -> dict:
        order_id = kwargs.get("order_id") if kwargs else None
        if not order_id and args:
            order_id = args[0]
        if not self.settings.toss_order_cancel_path:
            return self._live_order_error_response("Toss live order cancellation endpoint is not configured.")
        return self._authenticated_post(
            self.settings.toss_order_cancel_path,
            {"order_id": order_id},
            idempotency_key=f"cancel-{order_id}" if order_id else None,
        )

    def get_live_order_status(self, *args, **kwargs) -> dict:
        order_id = kwargs.get("order_id") if kwargs else None
        if not order_id and args:
            order_id = args[0]
        if not self.settings.toss_order_status_path:
            return self._live_order_error_response("Toss live order status endpoint is not configured.")
        path = self.settings.toss_order_status_path.format(order_id=parse.quote(str(order_id)))
        return self._authenticated_get(path)

    @staticmethod
    def _todo_live_order_response(message: str) -> dict:
        return {
            "success": False,
            "status": OrderStatus.TODO_LIVE_ORDER_NOT_IMPLEMENTED.value,
            "message": message,
            "live_order_blocked": True,
            "raw_response_saved": False,
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

    def _authenticated_post(
        self,
        path: str | None,
        payload: dict,
        *,
        idempotency_key: str | None = None,
        include_account_header: bool = True,
    ) -> dict:
        if not path:
            return self._live_order_error_response("Toss live order endpoint path is not configured.")

        token_result = self._issue_access_token()
        if not token_result["success"]:
            return token_result

        headers = {
            "Authorization": f"Bearer {token_result['access_token']}",
            "Content-Type": "application/json",
        }
        if include_account_header:
            headers[self.settings.toss_order_account_header_name] = self.settings.toss_account_id or ""
        if idempotency_key:
            headers[self.settings.toss_order_idempotency_header_name] = idempotency_key

        req = request.Request(
            self._url(path),
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=self.settings.toss_timeout_seconds) as response:
                body = json.loads(response.read().decode("utf-8"))
            return {
                "success": True,
                "status": "LIVE_ORDER_SUBMITTED",
                "data": body,
                "request_payload": self._safe_live_order_payload(payload),
                "idempotency_key": idempotency_key,
                "raw_response_saved": True,
            }
        except (error.HTTPError, error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            error_response = self._safe_error_response(exc)
            return {
                **error_response,
                "request_payload": self._safe_live_order_payload(payload),
                "idempotency_key": idempotency_key,
            }

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
        if self._access_token and time.monotonic() < self._access_token_expires_at:
            return {
                "success": True,
                "status": "OK",
                "access_token": self._access_token,
                "raw_response_saved": False,
                "cache_hit": True,
            }

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
            expires_in = self._safe_positive_int(body.get("expires_in"), default=300)
            self._access_token = access_token
            self._access_token_expires_at = time.monotonic() + max(expires_in - 30, 1)
            return {
                "success": True,
                "status": "OK",
                "access_token": access_token,
                "raw_response_saved": False,
            }
        except (error.HTTPError, error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            return self._safe_error_response(exc)

    @staticmethod
    def _safe_positive_int(value, default: int) -> int:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return default
        return parsed if parsed > 0 else default

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

    def _live_order_endpoint_ready(self) -> bool:
        return bool(
            not self.settings.use_mock_data
            and not self.settings.dry_run
            and self.settings.live_trading_enabled
            and self.settings.toss_credentials_ready
            and self.settings.toss_token_path
            and self.settings.toss_order_path
        )

    @staticmethod
    def _live_order_payload(order_intent: dict) -> dict:
        return {
            "account_id": order_intent.get("account_id"),
            "symbol": order_intent.get("symbol"),
            "side": order_intent.get("side"),
            "quantity": order_intent.get("quantity"),
            "price": order_intent.get("price"),
            "order_amount": order_intent.get("order_amount"),
            "order_sizing_mode": order_intent.get("order_sizing_mode"),
            "order_type": order_intent.get("order_type", "MARKET"),
            "fractional": order_intent.get("fractional_trading_enabled"),
            "client_order_id": order_intent.get("idempotency_key"),
            "metadata": {
                "decision_id": order_intent.get("decision_id"),
                "source": "ai_trading_agent",
            },
        }

    @staticmethod
    def _safe_live_order_payload(payload: dict) -> dict:
        return {
            key: value
            for key, value in payload.items()
            if key not in {"account_id"}
        }

    @staticmethod
    def _todo_read_only_response(message: str) -> dict:
        return {
            "success": False,
            "status": "TODO_READ_ONLY_API_NOT_CONFIGURED",
            "message": message,
            "raw_response_saved": False,
        }

    @staticmethod
    def _live_order_error_response(message: str) -> dict:
        return {
            "success": False,
            "status": "LIVE_ORDER_FAILED",
            "message": message,
            "raw_response_saved": False,
        }

    @staticmethod
    def _safe_error_response(exc: Exception) -> dict:
        http_status_code = exc.code if isinstance(exc, error.HTTPError) else None
        message = str(exc).replace("\n", " ")[:500]
        if http_status_code == 401:
            message = f"{message} Check Toss API credentials, token path, and account permissions."
        elif http_status_code == 429:
            message = f"{message} Toss rate limit reached. Wait briefly before retrying."
        return {
            "success": False,
            "status": "FAILED",
            "http_status_code": http_status_code,
            "message": message,
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
