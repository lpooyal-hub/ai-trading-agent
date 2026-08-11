from datetime import datetime, time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.config import Settings


def get_market_window(settings: Settings) -> dict:
    """Return {"open_now": bool, "session": str} for the configured market calendar.

    Shared by AgentScheduleService (external trigger gate) and the LangGraph
    loop_gate node (in-session continue/stop gate) so both read the same
    regular-session definition. See docs/plans/continuous-session-loop.md.
    """
    try:
        tz = ZoneInfo(settings.agent_market_timezone)
    except ZoneInfoNotFoundError:
        return {"open_now": False, "session": "INVALID_TIMEZONE"}

    now = datetime.now(tz)
    if now.date().isoformat() in settings.agent_market_closed_dates:
        return {"open_now": False, "session": "MARKET_CLOSED_DATE"}

    open_time = _parse_time(settings.agent_market_open_time)
    close_time = _parse_time(settings.agent_market_close_time)
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


def is_market_open(settings: Settings) -> bool:
    return get_market_window(settings)["open_now"]


def _parse_time(value: str) -> time | None:
    try:
        hour, minute = value.split(":", 1)
        return time(int(hour), int(minute))
    except (AttributeError, ValueError, TypeError):
        return None
