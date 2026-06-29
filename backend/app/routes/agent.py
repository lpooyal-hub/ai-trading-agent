from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import (
    AgentAutomationPolicyRead,
    AgentDecisionRead,
    AgentReadinessRead,
    AgentScheduleRead,
    AgentScheduledRunRead,
    AgentStatusRead,
)
from app.services.agent_schedule_service import AgentScheduleService
from app.services.agent_service import AgentService


router = APIRouter(prefix="/agent", tags=["agent"])


@router.post("/run-once", response_model=AgentDecisionRead)
def run_agent_once(db: Session = Depends(get_db)) -> AgentDecisionRead:
    service = AgentService()
    return service.run_once(db)


@router.post("/run-scheduled", response_model=AgentScheduledRunRead)
def run_scheduled_agent(db: Session = Depends(get_db)) -> AgentScheduledRunRead:
    schedule_service = AgentScheduleService()
    should_run, reason, schedule = schedule_service.should_run_now(db)
    if not should_run:
        return AgentScheduledRunRead(
            triggered=False,
            reason=reason,
            schedule=AgentScheduleRead(**schedule),
            decision=None,
        )

    decision = AgentService().run_once(db)
    return AgentScheduledRunRead(
        triggered=True,
        reason=reason,
        schedule=AgentScheduleRead(**schedule_service.get_schedule(db)),
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
    service = AgentScheduleService()
    return AgentScheduleRead(**service.get_schedule(db))


@router.get("/readiness", response_model=AgentReadinessRead)
def get_agent_readiness(db: Session = Depends(get_db)) -> AgentReadinessRead:
    service = AgentService()
    return AgentReadinessRead(**service.get_readiness(db))
