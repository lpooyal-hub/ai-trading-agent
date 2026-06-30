from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.agents.scheduler_agent import SchedulerAgent
from app.database import get_db
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
from app.services.agent_service import AgentService


router = APIRouter(prefix="/agent", tags=["agent"])


@router.post("/run-once", response_model=AgentDecisionRead)
def run_agent_once(db: Session = Depends(get_db)) -> AgentDecisionRead:
    service = AgentService()
    return service.run_once(db)


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
