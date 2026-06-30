from typing import Any

from sqlalchemy.orm import Session

from app.services.memory_service import MemoryService


class MemoryAgent:
    """Summarize past journaled outcomes for strategy feedback."""

    def __init__(self):
        self.memory_service = MemoryService()

    def get_summary(self, db: Session, limit: int = 100) -> dict[str, Any]:
        return self.memory_service.get_summary(db, limit=limit)
