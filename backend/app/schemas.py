from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models import (
    AgentAction,
    DecisionStatus,
    EvaluationWindow,
    OrderSide,
    OrderStatus,
)


class HealthResponse(BaseModel):
    status: str
    app_name: str
    dry_run: bool


class LegacyPositionBase(BaseModel):
    symbol: str
    name: str
    quantity: float
    avg_price: float
    source: str = "manual"
    is_protected: bool = True


class LegacyPositionCreate(LegacyPositionBase):
    pass


class LegacyPositionInitializeRequest(BaseModel):
    positions: list[LegacyPositionCreate]


class LegacyPositionRead(LegacyPositionBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    captured_at: datetime


class LegacyPositionInitializeResponse(BaseModel):
    initialized_count: int
    skipped_count: int
    positions: list[LegacyPositionRead]


class BrokerPositionRead(BaseModel):
    symbol: str
    name: str
    quantity: float
    avg_price: float
    current_price: float
    source: str


class BrokerAccountRead(BaseModel):
    masked_account_no: str
    account_seq: int | None = None
    account_type: str | None = None
    source: str


class BrokerAccountPreviewRead(BaseModel):
    success: bool
    status: str
    http_status_code: int | None = None
    message: str | None = None
    accounts: list[BrokerAccountRead]
    raw_response_saved: bool = False
    cache_hit: bool = False


class BrokerPositionPreviewRead(BaseModel):
    success: bool
    status: str
    http_status_code: int | None = None
    message: str | None = None
    positions: list[BrokerPositionRead]
    raw_response_saved: bool = False
    cache_hit: bool = False


class LegacyPositionBrokerSyncResponse(BaseModel):
    imported_count: int
    skipped_count: int
    success: bool
    status: str
    message: str | None = None
    positions: list[LegacyPositionRead]


class BotPositionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    symbol: str
    name: str
    sector: str
    quantity: float
    avg_buy_price: float
    total_invested_amount: float
    current_price: float
    unrealized_pnl: float
    unrealized_pnl_percent: float
    status: str
    created_at: datetime
    updated_at: datetime


class BotPositionMarketSyncResponse(BaseModel):
    updated_count: int
    skipped_count: int
    success: bool
    status: str
    message: str
    positions: list[BotPositionRead]


class PortfolioSummaryRead(BaseModel):
    bot_capital_limit_usd: float
    invested_amount_usd: float
    available_budget_usd: float
    min_cash_reserve_usd: float
    bot_position_count: int
    legacy_position_count: int
    protected_legacy_symbols: list[str]
    bot_symbols: list[str]
    unrealized_pnl_usd: float
    unrealized_pnl_percent: float
    dry_run: bool
    live_trading_enabled: bool
    use_mock_data: bool
    active_universe: list[str]


class PortfolioPerformanceRead(BaseModel):
    simulated_order_count: int
    buy_order_count: int
    sell_order_count: int
    gross_bought_usd: float
    gross_sold_usd: float
    realized_pnl_usd: float
    unrealized_pnl_usd: float
    total_pnl_usd: float
    total_pnl_percent: float
    winning_sell_count: int
    losing_sell_count: int
    win_rate_percent: float
    open_bot_position_count: int
    closed_bot_position_count: int


class PortfolioCostRecoveryRead(BaseModel):
    pnl_scope: str
    llm_cost_scope: str
    paper_total_pnl_usd: float
    paper_realized_pnl_usd: float
    monthly_llm_cost_usd: float
    today_llm_cost_usd: float
    net_after_llm_cost_usd: float
    realized_net_after_llm_cost_usd: float
    llm_cost_recovery_ratio: float | None
    realized_llm_cost_recovery_ratio: float | None
    llm_cost_covered: bool | None
    realized_llm_cost_covered: bool | None
    simulated_order_count: int
    today_llm_calls: int


class PortfolioRealizedTradeRead(BaseModel):
    order_id: int
    created_at: datetime
    symbol: str
    quantity: float
    sell_amount_usd: float
    cost_basis_usd: float
    realized_pnl_usd: float
    realized_pnl_percent: float


class PortfolioSymbolPerformanceRead(BaseModel):
    symbol: str
    realized_trade_count: int
    realized_pnl_usd: float
    sell_amount_usd: float
    win_rate_percent: float


class AgentDecisionBase(BaseModel):
    symbol: str
    sector: str
    action: AgentAction
    confidence: float = Field(ge=0, le=1)
    current_price: float
    recommended_order_amount: float = Field(ge=0)
    thesis: str
    risk_notes: str
    input_snapshot_json: dict[str, Any] = Field(default_factory=dict)
    agent_response_json: dict[str, Any] = Field(default_factory=dict)
    llm_model: str | None = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    estimated_llm_cost_usd: float = 0
    dry_run: bool = True


class AgentDecisionCreate(AgentDecisionBase):
    pass


class AgentDecisionRead(AgentDecisionBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    status: DecisionStatus
    rejection_reason: str | None
    executed_order_id: int | None


class DecisionRejectRequest(BaseModel):
    reason: str


class TradeJournalEntryCreate(BaseModel):
    decision_id: int
    order_id: int | None = None
    evaluation_id: int | None = None
    outcome_label: str = "PENDING_REVIEW"
    reward_score: float = 0
    agent_self_feedback: str | None = None
    lesson: str | None = None
    strategy_tags: list[str] = Field(default_factory=list)
    journal_json: dict[str, Any] = Field(default_factory=dict)


class TradeJournalEntryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    decision_id: int
    order_id: int | None
    evaluation_id: int | None
    symbol: str
    action: AgentAction
    outcome_label: str
    reward_score: float
    thesis_snapshot: str
    agent_self_feedback: str
    lesson: str | None
    strategy_tags_json: list[str]
    journal_json: dict[str, Any]


class MemoryGroupStatRead(BaseModel):
    key: str
    count: int
    win_rate_percent: float
    average_reward_score: float


class MemoryMistakeRead(BaseModel):
    mistake_type: str
    count: int


class MemoryLessonRead(BaseModel):
    journal_id: int
    symbol: str
    action: str
    reward_score: float
    lesson: str


class MemorySummaryRead(BaseModel):
    lookback_journal_entries: int
    evaluated_entry_count: int
    average_reward_score: float
    win_rate_percent: float
    action_stats: list[MemoryGroupStatRead]
    symbol_stats: list[MemoryGroupStatRead]
    model_stats: list[MemoryGroupStatRead]
    common_mistakes: list[MemoryMistakeRead]
    recent_lessons: list[MemoryLessonRead]
    memory_notes: list[str]
    data_gaps: list[str]


class DecisionPreviewRead(BaseModel):
    decision_id: int
    approved: bool
    reason: str
    symbol: str
    action: AgentAction
    side: OrderSide | None
    estimated_quantity: float
    estimated_price: float
    estimated_order_amount: float
    available_budget: float
    bot_exposure: float
    bot_owned_quantity: float
    legacy_protected: bool
    execution_mode: str
    dry_run: bool
    live_trading_enabled: bool
    warnings: list[str]


class AgentStatusRead(BaseModel):
    dry_run: bool
    use_mock_data: bool
    live_trading_enabled: bool
    automation_enabled: bool
    automation_mode: str
    paper_auto_enabled: bool
    active_universe: list[str]
    last_decision_id: int | None
    last_decision_status: str | None


class AgentAutomationPolicyRead(BaseModel):
    automation_enabled: bool
    automation_mode: str
    paper_auto_enabled: bool
    min_confidence: float
    max_order_amount_usd: float
    dry_run: bool
    live_trading_enabled: bool
    blockers: list[str]
    next_actions: list[str]


class AgentScheduleRead(BaseModel):
    scheduler_enabled: bool
    interval_minutes: int
    market_hours_only: bool
    market_timezone: str
    market_open_time: str
    market_close_time: str
    market_closed_dates: list[str]
    market_open_now: bool
    market_session: str
    due: bool
    last_decision_id: int | None
    last_run_at: datetime | None
    next_run_at: datetime | None
    minutes_until_next_run: int | None
    blockers: list[str]
    next_actions: list[str]


class AgentScheduledRunRead(BaseModel):
    triggered: bool
    reason: str
    schedule: AgentScheduleRead
    decision: AgentDecisionRead | None


class AgentOperationsRead(BaseModel):
    last_decision_id: int | None
    last_decision_status: str | None
    last_decision_symbol: str | None
    last_order_id: int | None
    last_order_status: str | None
    last_order_symbol: str | None
    last_evaluation_id: int | None
    last_evaluation_window: str | None
    pending_decision_count: int
    executable_decision_count: int
    simulated_order_count: int
    rejected_order_count: int
    failed_order_count: int
    latest_activity_at: datetime | None


class AgentCandidateRead(BaseModel):
    symbol: str
    score: float
    reason: str
    change_percent: float
    volume: float


class AgentReadinessRead(BaseModel):
    ready: bool
    reason: str
    automation_ready: bool
    automation_reason: str
    paper_auto_ready: bool
    paper_auto_reason: str
    llm_mode: str
    llm_blockers: list[str]
    dry_run: bool
    use_mock_data: bool
    real_llm_ready: bool
    market_ready: bool
    budget_ready: bool
    candidate_symbols: list[str]
    candidate_details: list[AgentCandidateRead]
    max_candidates_per_run: int
    fresh_symbol_count: int
    missing_symbols: list[str]
    llm_budget_reason: str


class TradeOrderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    decision_id: int
    created_at: datetime
    symbol: str
    side: OrderSide
    quantity: float
    price: float
    order_amount: float
    status: OrderStatus
    dry_run: bool
    reason: str
    raw_response_json: dict[str, Any]


class DecisionEvaluationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    decision_id: int
    evaluated_at: datetime
    evaluation_window: EvaluationWindow
    price_at_decision: float
    price_at_evaluation: float
    return_percent: float
    was_profitable: bool
    agent_self_review: str
    mistake_type: str | None
    improvement_note: str | None
    evaluation_json: dict[str, Any]


class EvaluationRunRequest(BaseModel):
    window: EvaluationWindow = EvaluationWindow.ONE_DAY


class EvaluationRunResponse(BaseModel):
    created_count: int
    evaluations: list[DecisionEvaluationRead]


class EvaluationWindowStatusRead(BaseModel):
    window: str
    eligible_count: int
    evaluated_count: int
    pending_count: int
    not_due_count: int
    coverage_percent: float


class EvaluationStatusRead(BaseModel):
    total_decisions: int
    total_evaluations: int
    latest_evaluated_at: datetime | None
    windows: list[EvaluationWindowStatusRead]


class MarketSnapshotRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    symbol: str
    price: float
    change_percent: float
    volume: float
    sector: str
    extra_json: dict[str, Any]


class MarketSnapshotCreate(BaseModel):
    symbol: str
    price: float = Field(gt=0)
    change_percent: float = 0
    volume: float = Field(ge=0)
    sector: str = "semiconductor"
    extra_json: dict[str, Any] = Field(default_factory=dict)


class MarketSnapshotBulkCreate(BaseModel):
    snapshots: list[MarketSnapshotCreate]


class MarketSnapshotBulkCreateResponse(BaseModel):
    created_count: int
    skipped_count: int
    snapshots: list[MarketSnapshotRead]


class MarketSnapshotRefreshResponse(BaseModel):
    created_count: int
    skipped_count: int
    source: str
    message: str
    snapshots: list[MarketSnapshotRead]


class MarketSnapshotStatusRead(BaseModel):
    active_universe: list[str]
    fresh_symbol_count: int
    missing_symbol_count: int
    missing_symbols: list[str]
    max_age_minutes: int
    ready_for_agent: bool
    message: str


class LLMUsageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    symbol: str | None
    decision_id: int | None
    evaluation_id: int | None
    model: str
    purpose: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_cost_usd: float
    latency_ms: int
    success: bool
    error_message: str | None
    raw_usage_json: dict[str, Any]


class LLMUsageSummaryRead(BaseModel):
    today_calls: int
    today_prompt_tokens: int
    today_completion_tokens: int
    today_total_tokens: int
    today_estimated_cost_usd: float
    monthly_estimated_cost_usd: float
    average_latency_ms: float
    successful_calls: int
    failed_calls: int
    last_call_at: datetime | None


class LLMBudgetRead(LLMUsageSummaryRead):
    approved: bool
    reason: str
    daily_cost_remaining_usd: float
    monthly_cost_remaining_usd: float
    daily_tokens_remaining: int
    daily_calls_remaining: int
    daily_cost_limit_usd: float
    monthly_cost_limit_usd: float
    daily_token_limit: int
    daily_call_limit: int
    min_minutes_between_calls: int
    cooldown_remaining_minutes: int


class LLMReadinessRead(BaseModel):
    real_llm_ready: bool
    llm_mode: str
    use_mock_data: bool
    openai_configured: bool
    llm_model_decision: str | None
    blockers: list[str]
    next_actions: list[str]


class LLMSmokeTestRead(BaseModel):
    success: bool
    model: str
    llm_mode: str
    latency_ms: int
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_cost_usd: float
    usage_id: int | None
    message: str


class DemoStatusRead(BaseModel):
    demo_enabled: bool
    demo_reason: str
    legacy_positions: int
    bot_positions: int
    decisions: int
    orders: int
    evaluations: int
    llm_usage_rows: int


class DemoSeedResponse(DemoStatusRead):
    created: bool
    message: str


class BrokerStatusRead(BaseModel):
    broker_provider: str
    use_mock_data: bool
    dry_run: bool
    live_trading_enabled: bool
    has_app_key: bool
    has_app_secret: bool
    has_account_id: bool
    api_credentials_ready: bool
    credentials_ready: bool
    account_lookup_ready: bool
    read_only_ready: bool
    openai_configured: bool
    real_llm_ready: bool
    live_ready: bool
    status_reason: str


class SafetySettingsRead(BaseModel):
    broker_provider: str
    dry_run: bool
    live_trading_enabled: bool
    use_mock_data: bool
    bot_capital_limit_usd: float
    max_order_amount_usd: float
    max_positions: int
    max_daily_trades: int
    min_cash_reserve_usd: float
    allowed_sector: str
    allowed_symbols: list[str]
    forbidden_keywords: list[str]
    protected_symbols: list[str]
    default_stop_mode: str
    hard_max_position_loss_percent: float
    hard_daily_loss_limit_percent: float
    llm_daily_call_limit: int
    llm_min_minutes_between_calls: int
    llm_max_candidates_per_run: int
    llm_model_decision: str | None
    llm_input_cost_per_1m_tokens_usd: float
    llm_output_cost_per_1m_tokens_usd: float
    openai_timeout_seconds: int
    real_llm_enabled: bool
    agent_automation_enabled: bool
    agent_automation_mode: str
    agent_auto_execute_min_confidence: float
    agent_auto_execute_max_order_amount_usd: float
    paper_auto_enabled: bool
    agent_scheduler_enabled: bool
    agent_scheduler_interval_minutes: int
    agent_scheduler_market_hours_only: bool
    agent_market_timezone: str
    agent_market_open_time: str
    agent_market_close_time: str
    agent_market_closed_dates: list[str]
    toss_base_url: str
    toss_token_path_configured: bool
    toss_accounts_path_configured: bool
    toss_positions_path_configured: bool
    market_snapshot_max_age_minutes: int


class SecurityReadinessRead(BaseModel):
    safe_for_public_demo: bool
    mock_data_enabled: bool
    dry_run_enabled: bool
    live_trading_enabled: bool
    toss_credentials_configured: bool
    toss_read_only_ready: bool
    openai_configured: bool
    real_llm_ready: bool
    warnings: list[str]
    next_actions: list[str]


class LiveTradingReadinessRead(BaseModel):
    live_order_ready: bool
    execution_mode: str
    dry_run_enabled: bool
    live_trading_enabled: bool
    mock_data_enabled: bool
    toss_credentials_ready: bool
    toss_read_only_ready: bool
    live_order_implementation: str
    adapter_checklist: list[str]
    blockers: list[str]
    next_actions: list[str]
