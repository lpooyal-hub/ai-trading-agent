from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.models import AgentDecision
from app.services.agent_schedule_service import AgentScheduleService
from app.services.agent_service import AgentRunLockedError, AgentService


@dataclass
class SchedulerAgentResult:
    triggered: bool
    reason: str
    schedule: dict
    decision: AgentDecision | None


class SchedulerAgent:
    """Decide whether the trading pipeline should run on this scheduler tick."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.schedule_service = AgentScheduleService(self.settings)

    def get_schedule(self, db: Session) -> dict:
        return self.schedule_service.get_schedule(db)

    def run_if_due(self, db: Session) -> SchedulerAgentResult:
        should_run, reason, schedule = self.schedule_service.should_run_now(db)
        if not should_run:
            return SchedulerAgentResult(
                triggered=False,
                reason=reason,
                schedule=schedule,
                decision=None,
            )

        try:
            decision = AgentService(self.settings).run_once(db)
        except AgentRunLockedError as exc:
            return SchedulerAgentResult(
                triggered=False,
                reason=str(exc),
                schedule=self.schedule_service.get_schedule(db),
                decision=None,
            )
        return SchedulerAgentResult(
            triggered=True,
            reason=reason,
            schedule=self.schedule_service.get_schedule(db),
            decision=decision,
        )
