from app.database import SessionLocal, init_db
from app.models import (
    AgentAction,
    AgentDecision,
    BotPosition,
    DecisionEvaluation,
    DecisionStatus,
    EvaluationWindow,
    LLMUsage,
    LLMPurpose,
    LegacyPosition,
    OrderSide,
    OrderStatus,
    TradeOrder,
)


def get_demo_status() -> dict:
    init_db()
    db = SessionLocal()
    try:
        return {
            "legacy_positions": db.query(LegacyPosition).count(),
            "bot_positions": db.query(BotPosition).count(),
            "decisions": db.query(AgentDecision).count(),
            "orders": db.query(TradeOrder).count(),
            "evaluations": db.query(DecisionEvaluation).count(),
            "llm_usage_rows": db.query(LLMUsage).count(),
        }
    finally:
        db.close()


def seed_demo_data() -> dict:
    """Seed fictional public-demo data only."""
    init_db()
    db = SessionLocal()
    try:
        if db.query(LegacyPosition).first():
            return {
                "created": False,
                "message": "Demo data already exists.",
                **get_demo_status(),
            }

        legacy = LegacyPosition(
            symbol="SPACE_X",
            name="Fictional Protected Legacy Position",
            quantity=1,
            avg_price=100000,
            source="fictional_demo_seed",
            is_protected=True,
        )
        bot_position = BotPosition(
            symbol="005930",
            name="Samsung Electronics Demo Position",
            sector="semiconductor",
            quantity=2,
            avg_buy_price=70000,
            total_invested_amount=140000,
            current_price=72000,
            unrealized_pnl=4000,
            unrealized_pnl_percent=2.86,
            status="OPEN",
        )
        decision = AgentDecision(
            symbol="005930",
            sector="semiconductor",
            action=AgentAction.HOLD,
            confidence=0.62,
            current_price=72000,
            recommended_order_amount=0,
            thesis="Fictional demo decision for public dashboard review.",
            risk_notes="Mock data only. No real order was placed.",
            input_snapshot_json={"source": "fictional_demo_seed"},
            agent_response_json={"source": "mock_llm_client"},
            llm_model="mock-llm",
            prompt_tokens=120,
            completion_tokens=80,
            total_tokens=200,
            estimated_llm_cost_usd=0,
            status=DecisionStatus.SKIPPED,
            rejection_reason="Demo data is paper-only.",
            dry_run=True,
        )
        db.add_all([legacy, bot_position, decision])
        db.flush()

        order = TradeOrder(
            decision_id=decision.id,
            symbol="005930",
            side=OrderSide.BUY,
            quantity=0,
            price=72000,
            order_amount=0,
            status=OrderStatus.SIMULATED,
            dry_run=True,
            reason="Fictional simulated demo order.",
            raw_response_json={"source": "fictional_demo_seed"},
        )
        evaluation = DecisionEvaluation(
            decision_id=decision.id,
            evaluation_window=EvaluationWindow.ONE_DAY,
            price_at_decision=72000,
            price_at_evaluation=72500,
            return_percent=0.69,
            was_profitable=True,
            agent_self_review="Fictional self-review for demo purposes.",
            mistake_type=None,
            improvement_note="Connect real paper-trading market data in a private setup.",
            evaluation_json={"source": "fictional_demo_seed"},
        )
        usage = LLMUsage(
            model="mock-llm",
            purpose=LLMPurpose.DECISION,
            symbol="005930",
            decision_id=decision.id,
            prompt_tokens=120,
            completion_tokens=80,
            total_tokens=200,
            estimated_cost_usd=0,
            latency_ms=12,
            success=True,
            raw_usage_json={"source": "fictional_demo_seed", "estimated": False},
        )
        db.add_all([order, evaluation, usage])
        db.commit()
        return {
            "created": True,
            "message": "Fictional demo data created.",
            **get_demo_status(),
        }
    finally:
        db.close()


if __name__ == "__main__":
    seed_demo_data()
