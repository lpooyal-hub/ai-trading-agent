import math
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.models import (
    AgentAction,
    AgentDecision,
    BotPosition,
    DecisionStatus,
    MarketSnapshot,
    OrderStatus,
    TradeJournalEntry,
    TradeOrder,
)
from app.risk.position_exit_manager import PositionExitManager, PositionExitSignal
from app.services.trading_service import TradingService


@dataclass(frozen=True)
class PositionExitExecution:
    symbol: str
    reason_code: str
    reason: str
    decision_id: int
    order_id: int | None
    order_status: str
    quantity: float
    price: float


@dataclass(frozen=True)
class PositionExitRunResult:
    policy_active: bool
    evaluated_count: int
    valuation_updated_count: int
    skipped_symbols: list[str]
    executions: list[PositionExitExecution]


class PositionExitService:
    """Refresh bot valuations and execute deterministic paper-only exits."""

    _FUTURE_TOLERANCE_SECONDS = 5

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.manager = PositionExitManager(self.settings)
        self.trading_service = TradingService(self.settings)

    def run(
        self,
        db: Session,
        snapshots: list[MarketSnapshot],
        *,
        observed_at: datetime | None = None,
    ) -> PositionExitRunResult:
        now = observed_at or datetime.utcnow()
        snapshot_by_symbol = self._fresh_snapshot_by_symbol(snapshots, now)
        positions = (
            db.query(BotPosition)
            .filter(BotPosition.status == "OPEN")
            .order_by(BotPosition.symbol.asc())
            .all()
        )
        policy_active = bool(self.settings.position_exit_enabled and self.settings.paper_auto_enabled)
        evaluated_count = 0
        valuation_updated_count = 0
        skipped_symbols: list[str] = []
        executions: list[PositionExitExecution] = []

        for position in positions:
            snapshot = snapshot_by_symbol.get(position.symbol.upper())
            if snapshot is None:
                skipped_symbols.append(position.symbol)
                continue

            self._refresh_position_valuation(position, snapshot.price)
            valuation_updated_count += 1
            if not policy_active:
                continue

            peak_price = self._peak_price(db, position, snapshot)
            signal = self.manager.evaluate(
                position,
                current_price=snapshot.price,
                peak_price=peak_price,
                observed_at=now,
            )
            evaluated_count += 1
            if signal is None:
                continue
            executions.append(self._execute_signal(db, position, signal))

        db.commit()
        return PositionExitRunResult(
            policy_active=policy_active,
            evaluated_count=evaluated_count,
            valuation_updated_count=valuation_updated_count,
            skipped_symbols=skipped_symbols,
            executions=executions,
        )

    def _execute_signal(
        self,
        db: Session,
        position: BotPosition,
        signal: PositionExitSignal,
    ) -> PositionExitExecution:
        order_amount = position.quantity * signal.current_price
        signal_payload = asdict(signal)
        decision = AgentDecision(
            symbol=position.symbol,
            sector=position.sector,
            action=AgentAction.SELL,
            confidence=1.0,
            current_price=signal.current_price,
            recommended_order_amount=order_amount,
            thesis=signal.reason,
            risk_notes="Deterministic paper-position risk exit; no LLM call was made.",
            input_snapshot_json={
                "source": "position_exit_manager",
                "position": {
                    "quantity": position.quantity,
                    "avg_buy_price": position.avg_buy_price,
                    "total_invested_amount": position.total_invested_amount,
                },
                "exit_signal": signal_payload,
            },
            agent_response_json={
                "source": "position_exit_manager",
                "action": AgentAction.SELL.value,
                "should_execute": True,
                "exit_signal": signal_payload,
            },
            llm_model=None,
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
            estimated_llm_cost_usd=0,
            status=DecisionStatus.PENDING,
            dry_run=True,
        )
        db.add(decision)
        db.flush()
        order = self.trading_service.execute_approved_decision(db, decision)
        self._journal_exit(db, decision, order, signal)
        return PositionExitExecution(
            symbol=position.symbol,
            reason_code=signal.reason_code,
            reason=signal.reason,
            decision_id=decision.id,
            order_id=order.id,
            order_status=order.status.value,
            quantity=order.quantity,
            price=order.price,
        )

    @staticmethod
    def _journal_exit(
        db: Session,
        decision: AgentDecision,
        order: TradeOrder,
        signal: PositionExitSignal,
    ) -> None:
        executed = order.status == OrderStatus.SIMULATED
        db.add(
            TradeJournalEntry(
                decision_id=decision.id,
                order_id=order.id,
                symbol=decision.symbol,
                action=AgentAction.SELL,
                outcome_label="RISK_EXIT_EXECUTED" if executed else "RISK_EXIT_REJECTED",
                reward_score=0,
                thesis_snapshot=decision.thesis,
                agent_self_feedback=(
                    "Deterministic paper exit executed without an LLM call."
                    if executed
                    else f"Deterministic exit was rejected: {order.reason}"
                ),
                strategy_tags_json=["position_exit", "paper_trading", signal.reason_code.lower()],
                journal_json={
                    "source": "position_exit_manager",
                    "exit_signal": asdict(signal),
                    "order_status": order.status.value,
                },
            )
        )
        db.commit()

    def _fresh_snapshot_by_symbol(
        self,
        snapshots: list[MarketSnapshot],
        observed_at: datetime,
    ) -> dict[str, MarketSnapshot]:
        result: dict[str, MarketSnapshot] = {}
        max_age = self.settings.position_exit_max_snapshot_age_seconds_safe
        for snapshot in snapshots:
            price = self._finite_float(getattr(snapshot, "price", None))
            created_at = getattr(snapshot, "created_at", None)
            symbol = str(getattr(snapshot, "symbol", "")).upper()
            if not symbol or price is None or price <= 0 or not isinstance(created_at, datetime):
                continue
            age_seconds = (observed_at - created_at).total_seconds()
            if age_seconds > max_age or age_seconds < -self._FUTURE_TOLERANCE_SECONDS:
                continue
            if not self.settings.use_mock_data:
                price_timestamp = self._parse_timestamp((snapshot.extra_json or {}).get("price_timestamp"))
                if price_timestamp is None:
                    continue
                observed_timestamp = self._utc_timestamp(observed_at)
                source_age_seconds = observed_timestamp - price_timestamp
                if (
                    source_age_seconds > max_age
                    or source_age_seconds < -self._FUTURE_TOLERANCE_SECONDS
                ):
                    continue
            previous = result.get(symbol)
            if previous is None or previous.created_at < created_at:
                result[symbol] = snapshot
        return result

    @staticmethod
    def _refresh_position_valuation(position: BotPosition, current_price: float) -> None:
        position.current_price = current_price
        position.unrealized_pnl = (current_price - position.avg_buy_price) * position.quantity
        position.unrealized_pnl_percent = (
            position.unrealized_pnl / position.total_invested_amount * 100
            if position.total_invested_amount
            else 0
        )

    @staticmethod
    def _peak_price(
        db: Session,
        position: BotPosition,
        snapshot: MarketSnapshot,
    ) -> float:
        peak = (
            db.query(func.max(MarketSnapshot.price))
            .filter(MarketSnapshot.symbol == position.symbol)
            .filter(MarketSnapshot.created_at >= position.created_at)
            .filter(MarketSnapshot.created_at <= snapshot.created_at)
            .scalar()
        )
        values = [position.avg_buy_price, snapshot.price]
        if peak is not None:
            values.append(float(peak))
        return max(values)

    @staticmethod
    def _finite_float(value) -> float | None:
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return None
        return parsed if math.isfinite(parsed) else None

    @staticmethod
    def _parse_timestamp(value) -> float | None:
        if value is None or isinstance(value, bool):
            return None
        if isinstance(value, (int, float)):
            return float(value) if math.isfinite(value) else None
        text = str(value).strip()
        if not text:
            return None
        try:
            parsed = datetime.fromisoformat(text)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.timestamp()
        except ValueError:
            pass
        try:
            parsed = float(text)
        except ValueError:
            return None
        return parsed if math.isfinite(parsed) else None

    @staticmethod
    def _utc_timestamp(value: datetime) -> float:
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.timestamp()
