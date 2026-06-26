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
            "openai_configured": openai_configured,
            "real_llm_ready": self.settings.real_llm_enabled,
            "live_ready": live_ready,
            "status_reason": self._status_reason(credentials_ready, live_ready),
        }

    def place_live_order(self, *args, **kwargs):
        # Live trading must stay behind explicit configuration and safety review.
        raise NotImplementedError("Real Toss Securities order execution is not connected yet.")

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
