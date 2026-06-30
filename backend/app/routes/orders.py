from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import OrderStatus, TradeOrder
from app.schemas import TradeOrderRead
from app.security import require_admin_api_key
from app.services.trading_service import TradingService


router = APIRouter(prefix="/orders", tags=["orders"])


@router.get("", response_model=list[TradeOrderRead])
def list_orders(
    status: OrderStatus | None = None,
    symbol: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[TradeOrderRead]:
    query = db.query(TradeOrder)
    if status:
        query = query.filter(TradeOrder.status == status)
    if symbol:
        query = query.filter(TradeOrder.symbol == symbol.upper())
    return query.order_by(TradeOrder.created_at.desc()).limit(limit).all()


@router.get("/{order_id}", response_model=TradeOrderRead)
def get_order(order_id: int, db: Session = Depends(get_db)) -> TradeOrderRead:
    order = db.get(TradeOrder, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found.")
    return order


@router.post("/{order_id}/sync-live-status", response_model=TradeOrderRead, dependencies=[Depends(require_admin_api_key)])
def sync_live_order_status(order_id: int, db: Session = Depends(get_db)) -> TradeOrderRead:
    order = db.get(TradeOrder, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found.")
    service = TradingService()
    return service.sync_live_order_status(db, order)
