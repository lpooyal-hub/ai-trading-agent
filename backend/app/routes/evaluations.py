from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import DecisionEvaluation, EvaluationWindow
from app.schemas import (
    DecisionEvaluationRead,
    EvaluationRunRequest,
    EvaluationRunResponse,
)
from app.services.evaluation_service import EvaluationService


router = APIRouter(prefix="/evaluations", tags=["evaluations"])


@router.post("/run", response_model=EvaluationRunResponse)
def run_due_evaluations(
    payload: EvaluationRunRequest | None = None,
    db: Session = Depends(get_db),
) -> EvaluationRunResponse:
    service = EvaluationService()
    window = payload.window if payload else EvaluationWindow.ONE_DAY
    evaluations = service.evaluate_all_due_decisions(db, window)
    return EvaluationRunResponse(
        created_count=len(evaluations),
        evaluations=evaluations,
    )


@router.post("/{decision_id}", response_model=DecisionEvaluationRead)
def evaluate_decision(
    decision_id: int,
    payload: EvaluationRunRequest | None = None,
    db: Session = Depends(get_db),
) -> DecisionEvaluationRead:
    service = EvaluationService()
    window = payload.window if payload else EvaluationWindow.ONE_DAY
    try:
        return service.evaluate_decision(db, decision_id, window)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("", response_model=list[DecisionEvaluationRead])
def list_evaluations(db: Session = Depends(get_db)) -> list[DecisionEvaluationRead]:
    return (
        db.query(DecisionEvaluation)
        .order_by(DecisionEvaluation.evaluated_at.desc())
        .all()
    )


@router.get("/{decision_id}", response_model=list[DecisionEvaluationRead])
def list_decision_evaluations(
    decision_id: int,
    db: Session = Depends(get_db),
) -> list[DecisionEvaluationRead]:
    return (
        db.query(DecisionEvaluation)
        .filter(DecisionEvaluation.decision_id == decision_id)
        .order_by(DecisionEvaluation.evaluated_at.desc())
        .all()
    )
