import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class AgentAction(str, enum.Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


class DecisionStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXECUTED = "EXECUTED"
    SKIPPED = "SKIPPED"


class OrderSide(str, enum.Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderStatus(str, enum.Enum):
    SIMULATED = "SIMULATED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"
    TODO_LIVE_ORDER_NOT_IMPLEMENTED = "TODO_LIVE_ORDER_NOT_IMPLEMENTED"


class EvaluationWindow(str, enum.Enum):
    ONE_DAY = "1d"
    THREE_DAYS = "3d"
    SEVEN_DAYS = "7d"
    THIRTY_DAYS = "30d"


class LLMPurpose(str, enum.Enum):
    DECISION = "decision"
    EVALUATION = "evaluation"
    REFLECTION = "reflection"
    SUMMARY = "summary"
    TEST = "test"


class LegacyPosition(Base):
    __tablename__ = "legacy_positions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    name: Mapped[str] = mapped_column(String(255))
    quantity: Mapped[float] = mapped_column(Float)
    avg_price: Mapped[float] = mapped_column(Float)
    captured_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    source: Mapped[str] = mapped_column(String(100), default="manual")
    is_protected: Mapped[bool] = mapped_column(Boolean, default=True)


class BotPosition(Base):
    __tablename__ = "bot_positions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    name: Mapped[str] = mapped_column(String(255))
    sector: Mapped[str] = mapped_column(String(100), index=True)
    quantity: Mapped[float] = mapped_column(Float)
    avg_buy_price: Mapped[float] = mapped_column(Float)
    total_invested_amount: Mapped[float] = mapped_column(Float)
    current_price: Mapped[float] = mapped_column(Float, default=0)
    unrealized_pnl: Mapped[float] = mapped_column(Float, default=0)
    unrealized_pnl_percent: Mapped[float] = mapped_column(Float, default=0)
    status: Mapped[str] = mapped_column(String(50), default="OPEN")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )


class AgentDecision(Base):
    __tablename__ = "agent_decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    sector: Mapped[str] = mapped_column(String(100), index=True)
    action: Mapped[AgentAction] = mapped_column(Enum(AgentAction))
    confidence: Mapped[float] = mapped_column(Float)
    current_price: Mapped[float] = mapped_column(Float)
    recommended_order_amount: Mapped[float] = mapped_column(Float, default=0)
    thesis: Mapped[str] = mapped_column(String(2000))
    risk_notes: Mapped[str] = mapped_column(String(2000))
    input_snapshot_json: Mapped[dict] = mapped_column(JSON, default=dict)
    agent_response_json: Mapped[dict] = mapped_column(JSON, default=dict)
    llm_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
    estimated_llm_cost_usd: Mapped[float] = mapped_column(Float, default=0)
    status: Mapped[DecisionStatus] = mapped_column(
        Enum(DecisionStatus),
        default=DecisionStatus.PENDING,
    )
    rejection_reason: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    executed_order_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("trade_orders.id"),
        nullable=True,
    )
    dry_run: Mapped[bool] = mapped_column(Boolean, default=True)

    orders: Mapped[list["TradeOrder"]] = relationship(
        back_populates="decision",
        foreign_keys="TradeOrder.decision_id",
    )
    executed_order: Mapped["TradeOrder | None"] = relationship(
        foreign_keys=[executed_order_id],
        post_update=True,
    )
    evaluations: Mapped[list["DecisionEvaluation"]] = relationship(
        back_populates="decision",
    )


class TradeOrder(Base):
    __tablename__ = "trade_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    decision_id: Mapped[int] = mapped_column(ForeignKey("agent_decisions.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    side: Mapped[OrderSide] = mapped_column(Enum(OrderSide))
    quantity: Mapped[float] = mapped_column(Float)
    price: Mapped[float] = mapped_column(Float)
    order_amount: Mapped[float] = mapped_column(Float)
    status: Mapped[OrderStatus] = mapped_column(Enum(OrderStatus))
    dry_run: Mapped[bool] = mapped_column(Boolean, default=True)
    reason: Mapped[str] = mapped_column(String(2000))
    raw_response_json: Mapped[dict] = mapped_column(JSON, default=dict)

    decision: Mapped[AgentDecision] = relationship(
        back_populates="orders",
        foreign_keys=[decision_id],
    )


class DecisionEvaluation(Base):
    __tablename__ = "decision_evaluations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    decision_id: Mapped[int] = mapped_column(ForeignKey("agent_decisions.id"))
    evaluated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    evaluation_window: Mapped[EvaluationWindow] = mapped_column(Enum(EvaluationWindow))
    price_at_decision: Mapped[float] = mapped_column(Float)
    price_at_evaluation: Mapped[float] = mapped_column(Float)
    return_percent: Mapped[float] = mapped_column(Float)
    was_profitable: Mapped[bool] = mapped_column(Boolean)
    agent_self_review: Mapped[str] = mapped_column(String(2000))
    mistake_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    improvement_note: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    evaluation_json: Mapped[dict] = mapped_column(JSON, default=dict)

    decision: Mapped[AgentDecision] = relationship(back_populates="evaluations")


class TradeJournalEntry(Base):
    __tablename__ = "trade_journal_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    decision_id: Mapped[int] = mapped_column(ForeignKey("agent_decisions.id"), index=True)
    order_id: Mapped[int | None] = mapped_column(ForeignKey("trade_orders.id"), nullable=True)
    evaluation_id: Mapped[int | None] = mapped_column(ForeignKey("decision_evaluations.id"), nullable=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    action: Mapped[AgentAction] = mapped_column(Enum(AgentAction))
    outcome_label: Mapped[str] = mapped_column(String(100), default="PENDING_REVIEW")
    reward_score: Mapped[float] = mapped_column(Float, default=0)
    thesis_snapshot: Mapped[str] = mapped_column(String(2000))
    agent_self_feedback: Mapped[str] = mapped_column(String(2000))
    lesson: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    strategy_tags_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    journal_json: Mapped[dict] = mapped_column(JSON, default=dict)

    decision: Mapped[AgentDecision] = relationship(foreign_keys=[decision_id])
    order: Mapped["TradeOrder | None"] = relationship(foreign_keys=[order_id])
    evaluation: Mapped["DecisionEvaluation | None"] = relationship(foreign_keys=[evaluation_id])


class MarketSnapshot(Base):
    __tablename__ = "market_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    price: Mapped[float] = mapped_column(Float)
    change_percent: Mapped[float] = mapped_column(Float)
    volume: Mapped[float] = mapped_column(Float)
    sector: Mapped[str] = mapped_column(String(100), index=True)
    extra_json: Mapped[dict] = mapped_column(JSON, default=dict)


class LLMUsage(Base):
    __tablename__ = "llm_usage"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    model: Mapped[str] = mapped_column(String(100))
    purpose: Mapped[LLMPurpose] = mapped_column(Enum(LLMPurpose))
    symbol: Mapped[str | None] = mapped_column(String(32), index=True, nullable=True)
    decision_id: Mapped[int | None] = mapped_column(
        ForeignKey("agent_decisions.id"),
        nullable=True,
    )
    evaluation_id: Mapped[int | None] = mapped_column(
        ForeignKey("decision_evaluations.id"),
        nullable=True,
    )
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
    estimated_cost_usd: Mapped[float] = mapped_column(Float, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    success: Mapped[bool] = mapped_column(Boolean, default=True)
    error_message: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    raw_usage_json: Mapped[dict] = mapped_column(JSON, default=dict)
