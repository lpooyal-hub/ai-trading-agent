from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.agents.evaluation_agent import EvaluationAgent
from app.database import get_db
from app.models import DecisionEvaluation, EvaluationWindow
from app.schemas import (
    DecisionEvaluationRead,
    EvaluationStatusRead,
    EvaluationRunRequest,
    EvaluationRunResponse,
)
from app.security import require_admin_api_key


router = APIRouter(prefix="/evaluations", tags=["evaluations"])


@router.post("/run", response_model=EvaluationRunResponse, dependencies=[Depends(require_admin_api_key)])
def run_due_evaluations(
    payload: EvaluationRunRequest | None = None,
    db: Session = Depends(get_db),
) -> EvaluationRunResponse:
    agent = EvaluationAgent()
    window = payload.window if payload else EvaluationWindow.ONE_DAY
    result = agent.run_due_evaluations(db, window)
    return EvaluationRunResponse(
        created_count=result.created_count,
        evaluations=result.evaluations,
    )


@router.get("/status", response_model=EvaluationStatusRead)
def get_evaluation_status(db: Session = Depends(get_db)) -> EvaluationStatusRead:
    return EvaluationStatusRead(**EvaluationAgent().get_status(db))


@router.post("/{decision_id}", response_model=DecisionEvaluationRead, dependencies=[Depends(require_admin_api_key)])
def evaluate_decision(
    decision_id: int,
    payload: EvaluationRunRequest | None = None,
    db: Session = Depends(get_db),
) -> DecisionEvaluationRead:
    agent = EvaluationAgent()
    window = payload.window if payload else EvaluationWindow.ONE_DAY
    try:
        return agent.evaluate_decision(db, decision_id, window)
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
