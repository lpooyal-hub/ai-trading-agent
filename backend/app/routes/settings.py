from fastapi import APIRouter

from app.config import get_settings
from app.schemas import SafetySettingsRead


router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/safety", response_model=SafetySettingsRead)
def get_safety_settings() -> SafetySettingsRead:
    settings = get_settings()
    return SafetySettingsRead(
        dry_run=settings.dry_run,
        live_trading_enabled=settings.live_trading_enabled,
        use_mock_data=settings.use_mock_data,
        bot_capital_limit_usd=settings.bot_capital_limit_usd,
        max_order_amount_usd=settings.max_order_amount_usd,
        max_positions=settings.max_positions,
        max_daily_trades=settings.max_daily_trades,
        min_cash_reserve_usd=settings.min_cash_reserve_usd,
        allowed_sector=settings.allowed_sector,
        allowed_symbols=settings.allowed_symbols,
        forbidden_keywords=settings.forbidden_keywords,
        protected_symbols=settings.protected_symbols,
        default_stop_mode=settings.default_stop_mode,
        hard_max_position_loss_percent=settings.hard_max_position_loss_percent,
        hard_daily_loss_limit_percent=settings.hard_daily_loss_limit_percent,
    )
