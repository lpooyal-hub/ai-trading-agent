from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.risk.llm_budget_manager import LLMBudgetManager
from app.schemas import LLMBudgetRead, SafetySettingsRead


router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/safety", response_model=SafetySettingsRead)
def get_safety_settings() -> SafetySettingsRead:
    settings = get_settings()
    return SafetySettingsRead(
        broker_provider=settings.broker_provider,
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
        llm_model_decision=settings.llm_model_decision,
        openai_timeout_seconds=settings.openai_timeout_seconds,
        real_llm_enabled=settings.real_llm_enabled,
    )


@router.get("/llm-budget", response_model=LLMBudgetRead)
def get_llm_budget_settings(db: Session = Depends(get_db)) -> LLMBudgetRead:
    settings = get_settings()
    budget = LLMBudgetManager(settings).check_budget(db)
    return LLMBudgetRead(
        **budget,
        daily_cost_limit_usd=settings.llm_daily_cost_limit_usd,
        monthly_cost_limit_usd=settings.llm_monthly_cost_limit_usd,
        daily_token_limit=settings.llm_daily_token_limit,
    )
