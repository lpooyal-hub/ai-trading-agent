from sqlalchemy.orm import Session

from app.models import TradeJournalEntry
from app.schemas import TradeJournalEntryCreate
from app.services.journal_service import JournalService


class JournalAgent:
    """Record and retrieve trade journals for later memory analysis."""

    def __init__(self):
        self.journal_service = JournalService()

    def list_entries(self, db: Session, limit: int = 50) -> list[TradeJournalEntry]:
        return self.journal_service.list_entries(db, limit=limit)

    def get_entry(self, db: Session, entry_id: int) -> TradeJournalEntry | None:
        return self.journal_service.get_entry(db, entry_id)

    def get_by_decision(self, db: Session, decision_id: int) -> list[TradeJournalEntry]:
        return self.journal_service.get_by_decision(db, decision_id)

    def create_entry(self, db: Session, payload: TradeJournalEntryCreate) -> TradeJournalEntry | None:
        return self.journal_service.create_entry(db, payload)
