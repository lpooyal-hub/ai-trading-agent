from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.models import AgentDecision


class AgentScheduleService:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    def get_schedule(self, db: Session) -> dict:
        latest_decision = self._latest_decision(db)
        last_run_at = latest_decision.created_at if latest_decision else None
        next_run_at = self._next_run_at(last_run_at)
        blockers = self._blockers()
        due = bool(self.settings.agent_scheduler_enabled and not blockers and self._is_due(next_run_at))
        return {
            "scheduler_enabled": self.settings.agent_scheduler_enabled,
            "interval_minutes": self.settings.agent_scheduler_interval_minutes_safe,
            "market_hours_only": self.settings.agent_scheduler_market_hours_only,
            "due": due,
            "last_decision_id": latest_decision.id if latest_decision else None,
            "last_run_at": last_run_at,
            "next_run_at": next_run_at,
            "minutes_until_next_run": self._minutes_until_next_run(next_run_at),
            "blockers": blockers,
            "next_actions": self._next_actions(blockers),
        }

    def should_run_now(self, db: Session) -> tuple[bool, str, dict]:
        schedule = self.get_schedule(db)
        if not self.settings.agent_scheduler_enabled:
            return False, "AGENT_SCHEDULER_ENABLED is false.", schedule
        if schedule["blockers"]:
            return False, " ".join(schedule["blockers"]), schedule
        if not schedule["due"]:
            return False, "Agent schedule is not due yet.", schedule
        return True, "Agent schedule is due.", schedule

    def _latest_decision(self, db: Session) -> AgentDecision | None:
        return (
            db.query(AgentDecision)
            .order_by(AgentDecision.created_at.desc())
            .first()
        )

    def _next_run_at(self, last_run_at: datetime | None) -> datetime | None:
        if not last_run_at:
            return None
        return last_run_at + timedelta(minutes=self.settings.agent_scheduler_interval_minutes_safe)

    @staticmethod
    def _is_due(next_run_at: datetime | None) -> bool:
        if not next_run_at:
            return True
        return datetime.utcnow() >= next_run_at

    @staticmethod
    def _minutes_until_next_run(next_run_at: datetime | None) -> int | None:
        if not next_run_at:
            return 0
        remaining_seconds = (next_run_at - datetime.utcnow()).total_seconds()
        if remaining_seconds <= 0:
            return 0
        return int((remaining_seconds + 59) // 60)

    def _blockers(self) -> list[str]:
        blockers: list[str] = []
        if self.settings.agent_scheduler_market_hours_only:
            blockers.append("Market-hours calendar is not implemented yet.")
        return blockers

    @staticmethod
    def _next_actions(blockers: list[str]) -> list[str]:
        if not blockers:
            return ["Call /agent/run-scheduled from cron or an external scheduler."]
        return [
            "Keep AGENT_SCHEDULER_MARKET_HOURS_ONLY=false for controlled paper automation testing.",
            "Add a market calendar before unattended production scheduling.",
        ]
