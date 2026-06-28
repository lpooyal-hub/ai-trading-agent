from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.clients.toss_client import TossClient
from app.schemas import (
    BotPositionMarketSyncResponse,
    BotPositionRead,
    LegacyPositionBrokerSyncResponse,
    LegacyPositionInitializeRequest,
    LegacyPositionInitializeResponse,
    LegacyPositionRead,
    PortfolioPerformanceRead,
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


@router.post("/sync-legacy-from-broker", response_model=LegacyPositionBrokerSyncResponse)
def sync_legacy_positions_from_broker(
    db: Session = Depends(get_db),
) -> LegacyPositionBrokerSyncResponse:
    broker_response = TossClient().get_positions()
    if not broker_response.get("success"):
        return LegacyPositionBrokerSyncResponse(
            imported_count=0,
            skipped_count=0,
            success=False,
            status=str(broker_response.get("status", "FAILED")),
            message=broker_response.get("message", "Broker positions could not be loaded."),
            positions=[],
        )

    service = PortfolioService()
    created, skipped_count, message = service.sync_legacy_positions_from_broker_payload(
        db,
        broker_response.get("data") or {},
    )
    return LegacyPositionBrokerSyncResponse(
        imported_count=len(created),
        skipped_count=skipped_count,
        success=message is None,
        status="IMPORTED" if message is None else "BLOCKED",
        message=message,
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


@router.post("/sync-bot-from-market", response_model=BotPositionMarketSyncResponse)
def sync_bot_positions_from_market(
    db: Session = Depends(get_db),
) -> BotPositionMarketSyncResponse:
    service = PortfolioService()
    updated, skipped_count, message = service.sync_bot_positions_from_market_snapshots(db)
    return BotPositionMarketSyncResponse(
        updated_count=len(updated),
        skipped_count=skipped_count,
        success=bool(updated),
        status="UPDATED" if updated else "NO_UPDATES",
        message=message,
        positions=updated,
    )


@router.get("/summary", response_model=PortfolioSummaryRead)
def get_portfolio_summary(db: Session = Depends(get_db)) -> PortfolioSummaryRead:
    service = PortfolioService()
    return PortfolioSummaryRead(**service.get_summary(db))


@router.get("/performance", response_model=PortfolioPerformanceRead)
def get_portfolio_performance(db: Session = Depends(get_db)) -> PortfolioPerformanceRead:
    service = PortfolioService()
    return PortfolioPerformanceRead(**service.get_performance(db))
