from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AgentDecision, DecisionStatus
from app.schemas import (
    AgentDecisionRead,
    DecisionPreviewRead,
    DecisionRejectRequest,
    TradeOrderRead,
)
from app.security import require_admin_api_key
from app.services.trading_service import TradingService


router = APIRouter(prefix="/decisions", tags=["decisions"])


@router.get("", response_model=list[AgentDecisionRead])
def list_decisions(
    status: DecisionStatus | None = None,
    symbol: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[AgentDecisionRead]:
    query = db.query(AgentDecision)
    if status:
        query = query.filter(AgentDecision.status == status)
    if symbol:
        query = query.filter(AgentDecision.symbol == symbol.upper())
    return query.order_by(AgentDecision.created_at.desc()).limit(limit).all()


@router.get("/{decision_id}", response_model=AgentDecisionRead)
def get_decision(decision_id: int, db: Session = Depends(get_db)) -> AgentDecisionRead:
    decision = _get_decision_or_404(db, decision_id)
    return decision


@router.get("/{decision_id}/preview", response_model=DecisionPreviewRead)
def preview_decision(decision_id: int, db: Session = Depends(get_db)) -> DecisionPreviewRead:
    decision = _get_decision_or_404(db, decision_id)
    service = TradingService()
    return DecisionPreviewRead(**service.preview_decision(db, decision))


@router.post("/{decision_id}/approve", response_model=TradeOrderRead, dependencies=[Depends(require_admin_api_key)])
def approve_decision(decision_id: int, db: Session = Depends(get_db)) -> TradeOrderRead:
    decision = _get_decision_or_404(db, decision_id)
    service = TradingService()
    return service.execute_approved_decision(db, decision)


@router.post("/{decision_id}/reject", response_model=AgentDecisionRead, dependencies=[Depends(require_admin_api_key)])
def reject_decision(
    decision_id: int,
    payload: DecisionRejectRequest,
    db: Session = Depends(get_db),
) -> AgentDecisionRead:
    decision = _get_decision_or_404(db, decision_id)
    decision.status = DecisionStatus.REJECTED
    decision.rejection_reason = payload.reason
    db.commit()
    db.refresh(decision)
    return decision


def _get_decision_or_404(db: Session, decision_id: int) -> AgentDecision:
    decision = db.get(AgentDecision, decision_id)
    if not decision:
        raise HTTPException(status_code=404, detail="Decision not found.")
    return decision
