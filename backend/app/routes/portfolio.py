from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import (
    BotPositionRead,
    LegacyPositionInitializeRequest,
    LegacyPositionInitializeResponse,
    LegacyPositionRead,
    PortfolioSummaryRead,
)
from app.services.portfolio_service import PortfolioService


router = APIRouter(prefix="/portfolio", tags=["portfolio"])


@router.post("/initialize-legacy", response_model=LegacyPositionInitializeResponse)
def initialize_legacy_positions(
    payload: LegacyPositionInitializeRequest,
    db: Session = Depends(get_db),
) -> LegacyPositionInitializeResponse:
    service = PortfolioService()
    created, skipped_count = service.initialize_legacy_positions(db, payload.positions)
    return LegacyPositionInitializeResponse(
        initialized_count=len(created),
        skipped_count=skipped_count,
        positions=created,
    )


@router.get("/legacy", response_model=list[LegacyPositionRead])
def list_legacy_positions(db: Session = Depends(get_db)) -> list[LegacyPositionRead]:
    service = PortfolioService()
    return service.list_legacy_positions(db)


@router.get("/bot", response_model=list[BotPositionRead])
def list_bot_positions(db: Session = Depends(get_db)) -> list[BotPositionRead]:
    service = PortfolioService()
    return service.list_bot_positions(db)


@router.get("/summary", response_model=PortfolioSummaryRead)
def get_portfolio_summary(db: Session = Depends(get_db)) -> PortfolioSummaryRead:
    service = PortfolioService()
    return PortfolioSummaryRead(**service.get_summary(db))
