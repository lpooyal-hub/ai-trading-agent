from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.agents.scheduler_agent import SchedulerAgent
from app.database import get_db
from app.models import AgentDecision
from app.schemas import (
    AgentAutomationPolicyRead,
    AgentDecisionRead,
    AgentOperationsRead,
    AgentReadinessRead,
    AgentScheduleRead,
    AgentScheduledRunRead,
    AgentStatusRead,
)
from app.services.agent_operations_service import AgentOperationsService
from app.services.agent_service import AgentRunLockedError, AgentService
from app.services.workflow_execution_service import WorkflowExecutionService


router = APIRouter(prefix="/agent", tags=["agent"])


@router.post("/run-once", response_model=AgentDecisionRead)
def run_agent_once(db: Session = Depends(get_db)) -> AgentDecisionRead:
    try:
        run = WorkflowExecutionService().run_once(db, trigger_source="agent_legacy")
    except AgentRunLockedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if run is None or run.decision_id is None:
        raise HTTPException(status_code=500, detail="Workflow run did not produce a decision.")
    decision = db.get(AgentDecision, run.decision_id)
    if decision is None:
        raise HTTPException(status_code=500, detail="Workflow decision was not found.")
    return decision


@router.post("/run-scheduled", response_model=AgentScheduledRunRead)
def run_scheduled_agent(db: Session = Depends(get_db)) -> AgentScheduledRunRead:
    result = SchedulerAgent().run_if_due(db)
    if not result.triggered:
        return AgentScheduledRunRead(
            triggered=False,
            reason=result.reason,
            schedule=AgentScheduleRead(**result.schedule),
            decision=None,
        )

    decision = result.decision
    if decision is None:
        return AgentScheduledRunRead(
            triggered=False,
            reason="Scheduler did not return a decision.",
            schedule=AgentScheduleRead(**result.schedule),
            decision=None,
        )

    return AgentScheduledRunRead(
        triggered=True,
        reason=result.reason,
        schedule=AgentScheduleRead(**result.schedule),
        decision=AgentDecisionRead.model_validate(decision),
    )


@router.get("/status", response_model=AgentStatusRead)
def get_agent_status(db: Session = Depends(get_db)) -> AgentStatusRead:
    service = AgentService()
    return AgentStatusRead(**service.get_status(db))


@router.get("/automation-policy", response_model=AgentAutomationPolicyRead)
def get_agent_automation_policy() -> AgentAutomationPolicyRead:
    service = AgentService()
    return AgentAutomationPolicyRead(**service.get_automation_policy())


@router.get("/schedule", response_model=AgentScheduleRead)
def get_agent_schedule(db: Session = Depends(get_db)) -> AgentScheduleRead:
    return AgentScheduleRead(**SchedulerAgent().get_schedule(db))


@router.get("/operations", response_model=AgentOperationsRead)
def get_agent_operations(db: Session = Depends(get_db)) -> AgentOperationsRead:
    service = AgentOperationsService()
    return AgentOperationsRead(**service.get_operations(db))


@router.get("/readiness", response_model=AgentReadinessRead)
def get_agent_readiness(db: Session = Depends(get_db)) -> AgentReadinessRead:
    service = AgentService()
    return AgentReadinessRead(**service.get_readiness(db))
