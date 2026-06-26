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


class DecisionPreviewRead(BaseModel):
    decision_id: int
    approved: bool
    reason: str
    available_budget: float
    dry_run: bool


class AgentStatusRead(BaseModel):
    dry_run: bool
    use_mock_data: bool
    live_trading_enabled: bool
    active_universe: list[str]
    last_decision_id: int | None
    last_decision_status: str | None


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


class LLMBudgetRead(LLMUsageSummaryRead):
    approved: bool
    reason: str
    daily_cost_remaining_usd: float
    monthly_cost_remaining_usd: float
    daily_tokens_remaining: int
    daily_cost_limit_usd: float
    monthly_cost_limit_usd: float
    daily_token_limit: int


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
