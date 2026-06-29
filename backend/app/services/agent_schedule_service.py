from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

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
        market_window = self._market_window()
        blockers = self._blockers(market_window)
        due = bool(self.settings.agent_scheduler_enabled and not blockers and self._is_due(next_run_at))
        return {
            "scheduler_enabled": self.settings.agent_scheduler_enabled,
            "interval_minutes": self.settings.agent_scheduler_interval_minutes_safe,
            "market_hours_only": self.settings.agent_scheduler_market_hours_only,
            "market_timezone": self.settings.agent_market_timezone,
            "market_open_time": self.settings.agent_market_open_time,
            "market_close_time": self.settings.agent_market_close_time,
            "market_open_now": market_window["open_now"],
            "market_session": market_window["session"],
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

    def _market_window(self) -> dict:
        try:
            tz = ZoneInfo(self.settings.agent_market_timezone)
        except ZoneInfoNotFoundError:
            return {"open_now": False, "session": "INVALID_TIMEZONE"}

        now = datetime.now(tz)
        open_time = self._parse_time(self.settings.agent_market_open_time)
        close_time = self._parse_time(self.settings.agent_market_close_time)
        if not open_time or not close_time or close_time <= open_time:
            return {"open_now": False, "session": "INVALID_MARKET_WINDOW"}
        is_weekday = now.weekday() < 5
        open_now = bool(is_weekday and open_time <= now.time() < close_time)
        if not is_weekday:
            session = "WEEKEND"
        elif now.time() < open_time:
            session = "PRE_MARKET"
        elif now.time() >= close_time:
            session = "AFTER_HOURS"
        else:
            session = "REGULAR"
        return {"open_now": open_now, "session": session}

    @staticmethod
    def _parse_time(value: str) -> time | None:
        try:
            hour, minute = value.split(":", 1)
            return time(int(hour), int(minute))
        except (AttributeError, ValueError, TypeError):
            return None

    def _blockers(self, market_window: dict) -> list[str]:
        blockers: list[str] = []
        if market_window["session"] == "INVALID_TIMEZONE":
            blockers.append("AGENT_MARKET_TIMEZONE is invalid.")
        if market_window["session"] == "INVALID_MARKET_WINDOW":
            blockers.append("AGENT_MARKET_OPEN_TIME or AGENT_MARKET_CLOSE_TIME is invalid.")
        if self.settings.agent_scheduler_market_hours_only and not market_window["open_now"]:
            blockers.append(f"Market is not in regular session: {market_window['session']}.")
        return blockers

    @staticmethod
    def _next_actions(blockers: list[str]) -> list[str]:
        if not blockers:
            return ["Call /agent/run-scheduled from cron or an external scheduler."]
        return [
            "Wait for the configured regular market session or set AGENT_SCHEDULER_MARKET_HOURS_ONLY=false for controlled paper testing.",
            "Add a holiday-aware market calendar before unattended production scheduling.",
        ]
