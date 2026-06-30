from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.models import WorkflowRun
from app.services.agent_service import AgentService
from app.services.workflow_service import WorkflowService


class WorkflowExecutionService:
    """Run the agentic workflow and return the recorded workflow run."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.agent_service = AgentService(self.settings)
        self.workflow_service = WorkflowService()

    def run_once(self, db: Session, trigger_source: str = "workflow") -> WorkflowRun | None:
        decision = self.agent_service.run_once(db, trigger_source=trigger_source)
        return self.workflow_service.get_latest_run_for_decision(db, decision.id)
