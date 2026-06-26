from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import LLMUsageRead, LLMUsageSummaryRead
from app.services.llm_usage_service import LLMUsageService


router = APIRouter(prefix="/llm-usage", tags=["llm-usage"])


@router.get("", response_model=list[LLMUsageRead])
def list_llm_usage(
    purpose: str | None = Query(default=None),
    symbol: str | None = Query(default=None),
    success: bool | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[LLMUsageRead]:
    service = LLMUsageService()
    return service.list_usage(db, purpose=purpose, symbol=symbol, success=success)


@router.get("/summary", response_model=LLMUsageSummaryRead)
def get_llm_usage_summary(db: Session = Depends(get_db)) -> LLMUsageSummaryRead:
    service = LLMUsageService()
    return LLMUsageSummaryRead(**service.summarize(db))


@router.get("/{usage_id}", response_model=LLMUsageRead)
def get_llm_usage(usage_id: int, db: Session = Depends(get_db)) -> LLMUsageRead:
    service = LLMUsageService()
    usage = service.get_usage(db, usage_id)
    if not usage:
        raise HTTPException(status_code=404, detail="LLM usage row not found.")
    return usage
