from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import OrderStatus, TradeOrder
from app.schemas import TradeOrderRead


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
