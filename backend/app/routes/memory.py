from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.agents.memory_agent import MemoryAgent
from app.database import get_db
from app.schemas import MemorySummaryRead


router = APIRouter(prefix="/memory", tags=["memory"])


@router.get("/summary", response_model=MemorySummaryRead)
def get_memory_summary(
    limit: int = 100,
    db: Session = Depends(get_db),
) -> MemorySummaryRead:
    return MemorySummaryRead(**MemoryAgent().get_summary(db, limit=limit))
