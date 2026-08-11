import unittest
from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import AgentSession, AgentSessionStatus
from app.services.agent_session_service import AgentSessionService


class AgentSessionServiceTest(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        self.service = AgentSessionService()

    def test_list_sessions_returns_latest_first(self):
        now = datetime.utcnow()
        with self.SessionLocal() as db:
            older = AgentSession(
                status=AgentSessionStatus.SUCCEEDED,
                trigger_source="worker",
                started_at=now - timedelta(hours=1),
                max_cycles=3,
            )
            newer = AgentSession(
                status=AgentSessionStatus.RUNNING,
                trigger_source="worker",
                started_at=now,
                max_cycles=3,
            )
            db.add_all([older, newer])
            db.commit()

            sessions = self.service.list_sessions(db)

        self.assertEqual([newer.id, older.id], [session.id for session in sessions])

    def test_get_session_returns_none_for_unknown_id(self):
        with self.SessionLocal() as db:
            self.assertIsNone(self.service.get_session(db, 999))

    def test_request_stop_sets_kill_switch_and_commits(self):
        with self.SessionLocal() as db:
            session = AgentSession(
                status=AgentSessionStatus.RUNNING,
                trigger_source="worker",
                max_cycles=3,
            )
            db.add(session)
            db.commit()
            session_id = session.id

            stopped = self.service.request_stop(db, session_id)
            db.expire_all()
            persisted = db.get(AgentSession, session_id)

        self.assertIsNotNone(stopped)
        self.assertIsNotNone(persisted)
        self.assertTrue(stopped.stop_requested)
        self.assertTrue(persisted.stop_requested)

    def test_request_stop_returns_none_for_unknown_id(self):
        with self.SessionLocal() as db:
            self.assertIsNone(self.service.request_stop(db, 999))


if __name__ == "__main__":
    unittest.main()
