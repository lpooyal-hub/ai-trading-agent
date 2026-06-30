from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import MemorySummaryRead
from app.services.memory_service import MemoryService


router = APIRouter(prefix="/memory", tags=["memory"])


@router.get("/summary", response_model=MemorySummaryRead)
def get_memory_summary(
    limit: int = 100,
    db: Session = Depends(get_db),
) -> MemorySummaryRead:
    return MemorySummaryRead(**MemoryService().get_summary(db, limit=limit))
