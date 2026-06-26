from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import TradeOrder
from app.schemas import TradeOrderRead


router = APIRouter(prefix="/orders", tags=["orders"])


@router.get("", response_model=list[TradeOrderRead])
def list_orders(db: Session = Depends(get_db)) -> list[TradeOrderRead]:
    return (
        db.query(TradeOrder)
        .order_by(TradeOrder.created_at.desc())
        .all()
    )


@router.get("/{order_id}", response_model=TradeOrderRead)
def get_order(order_id: int, db: Session = Depends(get_db)) -> TradeOrderRead:
    order = db.get(TradeOrder, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found.")
    return order
