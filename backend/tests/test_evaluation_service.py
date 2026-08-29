import unittest
from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import (
    AgentAction,
    AgentDecision,
    DecisionStatus,
    EvaluationWindow,
    MarketSnapshot,
)
from app.services.evaluation_service import EvaluationService


class EvaluationServiceTest(unittest.TestCase):
    def setUp(self):
        engine = create_engine(
            "sqlite:///:memory:", connect_args={"check_same_thread": False}
        )
        Base.metadata.create_all(bind=engine)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        self.db = self.SessionLocal()
        self.service = EvaluationService()

    def tearDown(self):
        self.db.close()

    def _decision(
        self,
        *,
        symbol: str,
        current_price: float,
        action: AgentAction = AgentAction.HOLD,
        status: DecisionStatus = DecisionStatus.SKIPPED,
        created_at: datetime | None = None,
    ) -> AgentDecision:
        decision = AgentDecision(
            created_at=created_at or (datetime.utcnow() - timedelta(days=2)),
            symbol=symbol,
            sector="internet",
            action=action,
            confidence=0.8,
            current_price=current_price,
            recommended_order_amount=0,
            thesis="t",
            risk_notes="r",
            input_snapshot_json={},
            agent_response_json={},
            status=status,
        )
        self.db.add(decision)
        self.db.commit()
        self.db.refresh(decision)
        return decision

    def test_pre_filter_skip_decisions_are_not_evaluable(self):
        skip = self._decision(symbol="NONE", current_price=0.0)
        real = self._decision(symbol="035420", current_price=215500.0)

        self.assertFalse(self.service._is_evaluable(skip))
        self.assertTrue(self.service._is_evaluable(real))

    def test_evaluate_all_due_decisions_skips_non_evaluable_backlog(self):
        for _ in range(5):
            self._decision(symbol="NONE", current_price=0.0)
        self._decision(symbol="035420", current_price=215500.0)

        evaluations = self.service.evaluate_all_due_decisions(
            self.db, EvaluationWindow.ONE_DAY
        )

        self.assertEqual(len(evaluations), 1)
        self.assertEqual(evaluations[0].decision.symbol, "035420")

    def test_resolve_price_uses_stored_snapshot_without_any_refresh(self):
        decision = self._decision(symbol="035420", current_price=200000.0)
        self.db.add(
            MarketSnapshot(
                symbol="035420",
                price=224500.0,
                change_percent=1.0,
                volume=1000,
                sector="internet",
                extra_json={},
            )
        )
        self.db.commit()

        # EvaluationService no longer holds a market client at all -- proves the
        # per-decision universe refresh path is gone.
        self.assertFalse(hasattr(self.service, "market_service"))
        self.assertEqual(
            self.service._resolve_evaluation_price(self.db, decision), 224500.0
        )

    def test_resolve_price_falls_back_to_decision_price_when_no_snapshot(self):
        decision = self._decision(symbol="035420", current_price=200000.0)
        self.assertEqual(
            self.service._resolve_evaluation_price(self.db, decision), 200000.0
        )

    def test_evaluate_decision_rejects_non_evaluable_decision(self):
        skip = self._decision(symbol="NONE", current_price=0.0)
        with self.assertRaises(ValueError):
            self.service.evaluate_decision(self.db, skip.id, EvaluationWindow.ONE_DAY)

    def test_status_counts_exclude_non_evaluable_decisions(self):
        for _ in range(3):
            self._decision(symbol="NONE", current_price=0.0)
        self._decision(symbol="035420", current_price=215500.0)

        status = self.service.get_status(self.db)

        self.assertEqual(status["total_decisions"], 1)
        one_day = next(
            w for w in status["windows"] if w["window"] == EvaluationWindow.ONE_DAY.value
        )
        self.assertEqual(one_day["eligible_count"], 1)


if __name__ == "__main__":
    unittest.main()
