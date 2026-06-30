from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.config import get_settings
from app.clients.llm_client import LLMClient
from app.database import get_db
from app.models import LLMPurpose
from app.risk.llm_budget_manager import LLMBudgetManager
from app.schemas import (
    LLMBudgetRead,
    LLMReadinessRead,
    LLMSmokeTestRead,
    LiveTradingReadinessRead,
    SafetySettingsRead,
    SecurityReadinessRead,
)
from app.services.llm_cost_service import LLMCostService
from app.services.llm_usage_service import LLMUsageService


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
        max_symbol_exposure_percent=settings.max_symbol_exposure_percent,
        min_cash_reserve_usd=settings.min_cash_reserve_usd,
        fractional_trading_enabled=settings.fractional_trading_enabled,
        min_order_amount_usd=settings.min_order_amount_usd,
        quantity_decimal_places=settings.quantity_decimal_places_safe,
        order_sizing_mode=settings.order_sizing_mode_normalized,
        allowed_sector=settings.allowed_sector,
        allowed_symbols=settings.allowed_symbols,
        forbidden_keywords=settings.forbidden_keywords,
        protected_symbols=settings.protected_symbols,
        default_stop_mode=settings.default_stop_mode,
        hard_max_position_loss_percent=settings.hard_max_position_loss_percent,
        hard_daily_loss_limit_percent=settings.hard_daily_loss_limit_percent,
        llm_daily_call_limit=settings.llm_daily_call_limit,
        llm_min_minutes_between_calls=settings.llm_min_minutes_between_calls,
        llm_max_candidates_per_run=settings.llm_max_candidates_per_run_safe,
        llm_model_decision=settings.llm_model_decision,
        llm_input_cost_per_1m_tokens_usd=settings.llm_input_cost_per_1m_tokens_usd,
        llm_output_cost_per_1m_tokens_usd=settings.llm_output_cost_per_1m_tokens_usd,
        openai_timeout_seconds=settings.openai_timeout_seconds,
        real_llm_enabled=settings.real_llm_enabled,
        agent_automation_enabled=settings.agent_automation_enabled,
        agent_automation_mode=settings.agent_automation_mode_normalized,
        agent_auto_execute_min_confidence=settings.agent_auto_execute_min_confidence,
        agent_auto_execute_max_order_amount_usd=settings.agent_auto_execute_max_order_amount_usd,
        paper_auto_enabled=settings.paper_auto_enabled,
        agent_scheduler_enabled=settings.agent_scheduler_enabled,
        agent_scheduler_interval_minutes=settings.agent_scheduler_interval_minutes_safe,
        agent_scheduler_market_hours_only=settings.agent_scheduler_market_hours_only,
        agent_market_timezone=settings.agent_market_timezone,
        agent_market_open_time=settings.agent_market_open_time,
        agent_market_close_time=settings.agent_market_close_time,
        agent_market_closed_dates=settings.agent_market_closed_dates,
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
        warnings.append("LIVE_TRADING_ENABLED is true, but BlockedLiveExecutionAdapter still prevents real orders.")
    if settings.use_mock_data and settings.has_external_api_credentials:
        warnings.append("Mock mode is enabled while external API credentials are configured.")
    if not settings.use_mock_data and not settings.toss_api_credentials_ready:
        next_actions.append("Configure Toss API key and secret or turn USE_MOCK_DATA back on.")
    if settings.toss_api_credentials_ready and not settings.toss_account_id:
        next_actions.append("Set TOSS_ACCOUNT_ID to enable holdings lookup and legacy sync.")
    if settings.toss_credentials_ready and not settings.toss_read_only_ready:
        next_actions.append("Configure Toss read-only endpoint paths before using holdings lookup or legacy sync.")
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


@router.get("/live-readiness", response_model=LiveTradingReadinessRead)
def get_live_trading_readiness() -> LiveTradingReadinessRead:
    settings = get_settings()
    blockers: list[str] = []
    next_actions: list[str] = []

    if settings.dry_run:
        blockers.append("DRY_RUN is true.")
        next_actions.append("Keep DRY_RUN=true until BlockedLiveExecutionAdapter is replaced after review.")
    if not settings.live_trading_enabled:
        blockers.append("LIVE_TRADING_ENABLED is false.")
    if settings.use_mock_data:
        blockers.append("USE_MOCK_DATA is true.")
    if not settings.toss_credentials_ready:
        blockers.append("Toss API credentials or TOSS_ACCOUNT_ID are incomplete.")
    if not settings.toss_read_only_ready:
        blockers.append("Toss read-only readiness is incomplete.")

    blockers.append("BlockedLiveExecutionAdapter is active.")
    next_actions.append("Replace the blocked-live adapter only after a separate broker order adapter review.")
    adapter_checklist = [
        "Map internal BUY/SELL order intent to Toss order request fields.",
        "Confirm account scope, order endpoint path, and required headers from official Toss docs.",
        "Add idempotency or duplicate-submit protection before any real order call.",
        "Persist masked broker response metadata without storing secrets.",
        "Add a broker adapter test plan before replacing BlockedLiveExecutionAdapter.",
        "Run manual broker sandbox or minimum-size production validation outside public demo mode.",
    ]

    return LiveTradingReadinessRead(
        live_order_ready=False,
        execution_mode="LIVE_ORDER_BLOCKED",
        dry_run_enabled=settings.dry_run,
        live_trading_enabled=settings.live_trading_enabled,
        mock_data_enabled=settings.use_mock_data,
        toss_credentials_ready=settings.toss_credentials_ready,
        toss_read_only_ready=settings.toss_read_only_ready,
        live_order_implementation="BlockedLiveExecutionAdapter",
        adapter_checklist=adapter_checklist,
        blockers=blockers,
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
        daily_call_limit=settings.llm_daily_call_limit,
        min_minutes_between_calls=settings.llm_min_minutes_between_calls,
    )


@router.get("/llm-readiness", response_model=LLMReadinessRead)
def get_llm_readiness() -> LLMReadinessRead:
    settings = get_settings()
    return LLMReadinessRead(
        real_llm_ready=settings.real_llm_enabled,
        llm_mode=settings.llm_mode,
        use_mock_data=settings.use_mock_data,
        openai_configured=bool(settings.openai_api_key),
        llm_model_decision=settings.llm_model_decision,
        blockers=settings.llm_readiness_blockers,
        next_actions=settings.llm_readiness_next_actions,
    )


@router.post("/llm-smoke-test", response_model=LLMSmokeTestRead)
def run_llm_smoke_test(db: Session = Depends(get_db)) -> LLMSmokeTestRead:
    settings = get_settings()
    budget = LLMBudgetManager(settings).check_budget(db)
    if not budget["approved"]:
        return LLMSmokeTestRead(
            success=False,
            model=settings.llm_model_decision or "unconfigured",
            llm_mode=settings.llm_mode,
            latency_ms=0,
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
            estimated_cost_usd=0,
            usage_id=None,
            message=f"LLM budget blocked: {budget['reason']}",
        )

    result = LLMClient(settings).smoke_test()
    prompt_tokens = int(result.usage.get("prompt_tokens", 0))
    completion_tokens = int(result.usage.get("completion_tokens", 0))
    total_tokens = int(result.usage.get("total_tokens", prompt_tokens + completion_tokens))
    estimated_cost = LLMCostService(settings).estimate_cost_usd(prompt_tokens, completion_tokens)
    usage = LLMUsageService().record_usage(
        db,
        model=settings.llm_model_decision or "unconfigured",
        purpose=LLMPurpose.TEST,
        symbol=None,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        estimated_cost_usd=estimated_cost,
        latency_ms=result.latency_ms,
        success=result.success,
        error_message=result.error_message,
        raw_usage_json=result.usage,
    )
    return LLMSmokeTestRead(
        success=result.success,
        model=settings.llm_model_decision or "unconfigured",
        llm_mode=settings.llm_mode,
        latency_ms=result.latency_ms,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        estimated_cost_usd=estimated_cost,
        usage_id=usage.id,
        message="OpenAI smoke test succeeded." if result.success else result.error_message or "OpenAI smoke test failed.",
    )
