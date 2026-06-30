from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.agents.journal_agent import JournalAgent
from app.database import get_db
from app.schemas import TradeJournalEntryCreate, TradeJournalEntryRead


router = APIRouter(prefix="/journal", tags=["journal"])


@router.get("", response_model=list[TradeJournalEntryRead])
def list_journal_entries(
    limit: int = 50,
    db: Session = Depends(get_db),
) -> list[TradeJournalEntryRead]:
    return JournalAgent().list_entries(db, limit=limit)


@router.post("", response_model=TradeJournalEntryRead)
def create_journal_entry(
    payload: TradeJournalEntryCreate,
    db: Session = Depends(get_db),
) -> TradeJournalEntryRead:
    entry = JournalAgent().create_entry(db, payload)
    if not entry:
        raise HTTPException(status_code=404, detail="Decision or linked journal reference was not found.")
    return entry


@router.get("/decision/{decision_id}", response_model=list[TradeJournalEntryRead])
def list_journal_entries_for_decision(
    decision_id: int,
    db: Session = Depends(get_db),
) -> list[TradeJournalEntryRead]:
    return JournalAgent().get_by_decision(db, decision_id)


@router.get("/{entry_id}", response_model=TradeJournalEntryRead)
def get_journal_entry(
    entry_id: int,
    db: Session = Depends(get_db),
) -> TradeJournalEntryRead:
    entry = JournalAgent().get_entry(db, entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Journal entry was not found.")
    return entry
