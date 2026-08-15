import unittest
from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import AgentAction, AgentDecision, TradeJournalEntry
from app.services.memory_service import MemoryService


class MemoryServiceStrategyEntryTest(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def test_guard_audits_do_not_push_older_executed_evidence_out_of_memory(self):
        now = datetime.utcnow()
        with self.SessionLocal() as db:
            skipped_decision = self._decision("NONE", AgentAction.HOLD)
            executed_decision = self._decision("005930", AgentAction.BUY)
            db.add_all([skipped_decision, executed_decision])
            db.flush()
            db.add(
                TradeJournalEntry(
                    created_at=now - timedelta(days=1),
                    decision_id=executed_decision.id,
                    order_id=999,
                    symbol="005930",
                    action=AgentAction.BUY,
                    outcome_label="PENDING_REVIEW",
                    reward_score=0,
                    thesis_snapshot="Executed paper entry.",
                    agent_self_feedback="Await evaluation.",
                    lesson="Use only outcome-backed evidence.",
                )
            )
            for index in range(100):
                db.add(
                    TradeJournalEntry(
                        created_at=now + timedelta(seconds=index),
                        decision_id=skipped_decision.id,
                        symbol="NONE",
                        action=AgentAction.HOLD,
                        outcome_label="SKIPPED_GUARD",
                        reward_score=0,
                        thesis_snapshot="No candidate.",
                        agent_self_feedback="Guard audit.",
                    )
                )
            db.commit()

            summary = MemoryService().get_summary(db, limit=100)

        self.assertEqual(summary["lookback_journal_entries"], 100)
        self.assertEqual(summary["strategy_entry_count"], 1)
        self.assertEqual(summary["action_stats"][0]["key"], "BUY")
        self.assertEqual(summary["recent_lessons"][0]["symbol"], "005930")

    @staticmethod
    def _decision(symbol: str, action: AgentAction) -> AgentDecision:
        return AgentDecision(
            symbol=symbol,
            sector="test",
            action=action,
            confidence=0.8,
            current_price=10000,
            recommended_order_amount=10000 if action == AgentAction.BUY else 0,
            thesis="test decision",
            risk_notes="test risk",
            input_snapshot_json={},
            agent_response_json={},
            dry_run=True,
        )


if __name__ == "__main__":
    unittest.main()
