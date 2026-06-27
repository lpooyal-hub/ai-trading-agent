from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import AgentDecisionRead, AgentReadinessRead, AgentStatusRead
from app.services.agent_service import AgentService


router = APIRouter(prefix="/agent", tags=["agent"])


@router.post("/run-once", response_model=AgentDecisionRead)
def run_agent_once(db: Session = Depends(get_db)) -> AgentDecisionRead:
    service = AgentService()
    return service.run_once(db)


@router.get("/status", response_model=AgentStatusRead)
def get_agent_status(db: Session = Depends(get_db)) -> AgentStatusRead:
    service = AgentService()
    return AgentStatusRead(**service.get_status(db))


@router.get("/readiness", response_model=AgentReadinessRead)
def get_agent_readiness(db: Session = Depends(get_db)) -> AgentReadinessRead:
    service = AgentService()
    return AgentReadinessRead(**service.get_readiness(db))
