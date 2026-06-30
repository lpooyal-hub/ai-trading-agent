from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import (
    MarketSnapshotBulkCreate,
    MarketSnapshotBulkCreateResponse,
    MarketSnapshotRead,
    MarketSnapshotRefreshResponse,
    MarketSnapshotStatusRead,
)
from app.security import require_admin_api_key
from app.services.market_service import MarketService


router = APIRouter(prefix="/market", tags=["market"])


@router.get("/snapshots", response_model=list[MarketSnapshotRead])
def list_market_snapshots(db: Session = Depends(get_db)) -> list[MarketSnapshotRead]:
    return MarketService().list_recent_snapshots(db)


@router.get("/snapshots/latest", response_model=list[MarketSnapshotRead])
def list_latest_universe_snapshots(db: Session = Depends(get_db)) -> list[MarketSnapshotRead]:
    return MarketService().get_latest_universe_snapshots(db)


@router.get("/snapshots/status", response_model=MarketSnapshotStatusRead)
def get_market_snapshot_status(db: Session = Depends(get_db)) -> MarketSnapshotStatusRead:
    result = MarketService().get_snapshot_status(db)
    return MarketSnapshotStatusRead(**result)


@router.post("/snapshots", response_model=MarketSnapshotBulkCreateResponse, dependencies=[Depends(require_admin_api_key)])
def create_market_snapshots(
    payload: MarketSnapshotBulkCreate,
    db: Session = Depends(get_db),
) -> MarketSnapshotBulkCreateResponse:
    created, skipped_count = MarketService().create_snapshots(db, payload.snapshots)
    return MarketSnapshotBulkCreateResponse(
        created_count=len(created),
        skipped_count=skipped_count,
        snapshots=created,
    )


@router.post("/snapshots/refresh", response_model=MarketSnapshotRefreshResponse, dependencies=[Depends(require_admin_api_key)])
def refresh_market_snapshots(db: Session = Depends(get_db)) -> MarketSnapshotRefreshResponse:
    result = MarketService().refresh_active_universe_snapshot_result(db)
    return MarketSnapshotRefreshResponse(**result)
