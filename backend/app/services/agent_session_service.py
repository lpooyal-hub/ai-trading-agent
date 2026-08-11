from sqlalchemy.orm import Session

from app.models import AgentSession


class AgentSessionService:
    def list_sessions(self, db: Session, limit: int = 50) -> list[AgentSession]:
        safe_limit = min(max(limit, 1), 200)
        return (
            db.query(AgentSession)
            .order_by(AgentSession.started_at.desc())
            .limit(safe_limit)
            .all()
        )

    def get_session(self, db: Session, session_id: int) -> AgentSession | None:
        return db.get(AgentSession, session_id)

    def request_stop(self, db: Session, session_id: int) -> AgentSession | None:
        session = self.get_session(db, session_id)
        if session is None:
            return None
        session.stop_requested = True
        db.commit()
        db.refresh(session)
        return session
