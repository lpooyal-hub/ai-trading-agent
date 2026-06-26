from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.risk.llm_budget_manager import LLMBudgetManager
from app.schemas import LLMBudgetRead, SafetySettingsRead, SecurityReadinessRead


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
        llm_input_cost_per_1m_tokens_usd=settings.llm_input_cost_per_1m_tokens_usd,
        llm_output_cost_per_1m_tokens_usd=settings.llm_output_cost_per_1m_tokens_usd,
        openai_timeout_seconds=settings.openai_timeout_seconds,
        real_llm_enabled=settings.real_llm_enabled,
        toss_base_url=settings.toss_base_url,
        toss_token_path_configured=bool(settings.toss_token_path),
        toss_accounts_path_configured=bool(settings.toss_accounts_path),
        toss_positions_path_configured=bool(settings.toss_positions_path),
        market_snapshot_max_age_minutes=settings.market_snapshot_max_age_minutes,
    )


@router.get("/security-readiness", response_model=SecurityReadinessRead)
def get_security_readiness() -> SecurityReadinessRead:
    settings = get_settings()
    warnings: list[str] = []
    next_actions: list[str] = []

    if not settings.dry_run:
        warnings.append("DRY_RUN is disabled. Review all order paths before running the agent.")
    if settings.live_trading_enabled:
        warnings.append("LIVE_TRADING_ENABLED is true. Public V1 still has no live order implementation.")
    if settings.use_mock_data and settings.has_external_api_credentials:
        warnings.append("Mock mode is enabled while external API credentials are configured.")
    if not settings.use_mock_data and not settings.toss_credentials_ready:
        next_actions.append("Configure Toss API credentials or turn USE_MOCK_DATA back on.")
    if settings.toss_credentials_ready and not settings.toss_read_only_ready:
        next_actions.append("Configure Toss read-only endpoint paths before using broker account or position lookup.")
    if not settings.real_llm_enabled:
        next_actions.append("Set USE_MOCK_DATA=false, OPENAI_API_KEY, and LLM_MODEL_DECISION to enable real LLM calls.")
    if settings.real_llm_enabled:
        next_actions.append("Run the agent with small DRY_RUN decisions first and review LLM usage cost logs.")

    safe_for_public_demo = settings.use_mock_data and settings.dry_run and not settings.has_external_api_credentials
    return SecurityReadinessRead(
        safe_for_public_demo=safe_for_public_demo,
        mock_data_enabled=settings.use_mock_data,
        dry_run_enabled=settings.dry_run,
        live_trading_enabled=settings.live_trading_enabled,
        toss_credentials_configured=settings.toss_credentials_ready,
        toss_read_only_ready=settings.toss_read_only_ready,
        openai_configured=bool(settings.openai_api_key),
        real_llm_ready=settings.real_llm_enabled,
        warnings=warnings,
        next_actions=next_actions,
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
