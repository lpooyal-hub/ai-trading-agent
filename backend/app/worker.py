import time
from collections.abc import Callable

from app.config import Settings, get_settings
from app.database import SessionLocal, init_db
from app.services.agent_graph_service import AgentGraphService
from app.utils.logger import get_logger
from app.utils.market_hours import get_market_window


logger = get_logger(__name__)
MARKET_POLL_SECONDS = 60.0

# get_market_window() "session" values that mean there is no regular session
# left to wait for today (weekend, holiday, already past close, or a bad
# market-window config). A one-shot cron-triggered run should exit rather
# than poll until the next calendar day.
_TERMINAL_SESSIONS = {
    "WEEKEND",
    "MARKET_CLOSED_DATE",
    "AFTER_HOURS",
    "INVALID_TIMEZONE",
    "INVALID_MARKET_WINDOW",
}


def wait_for_todays_market_open(
    settings: Settings,
    *,
    poll_seconds: float = MARKET_POLL_SECONDS,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> bool:
    """Poll until today's regular session opens. Returns False without
    blocking further once today has no session left (see _TERMINAL_SESSIONS),
    so a single invocation never hangs into the next calendar day."""
    delay = max(float(poll_seconds), 1.0)
    while True:
        window = get_market_window(settings)
        if window["open_now"]:
            return True
        if window["session"] in _TERMINAL_SESSIONS:
            return False
        sleep_fn(delay)


def run_agent_session(graph_service: AgentGraphService):
    with SessionLocal() as db:
        return graph_service.run_session(db, trigger_source="worker")


def run_worker_once(
    settings: Settings | None = None,
    *,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> None:
    """One cron-triggered invocation: wait for today's market open (if not
    already open), run a single session end-to-end, then return.

    Intended to be invoked once per day by an external scheduler (host cron
    running `docker compose run --rm worker`), not left running as a
    long-lived daemon across multiple days — the multi-cycle loop itself is
    owned by AgentGraphService.run_session(), not by this process. See
    docs/plans/continuous-session-loop.md.
    """
    worker_settings = settings or get_settings()

    if not worker_settings.agent_scheduler_enabled:
        logger.info(
            "Agent scheduler is disabled (agent_scheduler_enabled=False); worker exiting without running."
        )
        return

    logger.info(
        "Agent session worker invoked (market_timezone=%s).",
        worker_settings.agent_market_timezone,
    )

    if not wait_for_todays_market_open(worker_settings, sleep_fn=sleep_fn):
        logger.info("No regular session left to wait for today; worker exiting.")
        return

    graph_service = AgentGraphService()
    try:
        session = run_agent_session(graph_service)
        logger.info(
            "Agent session %s ended with status=%s, cycles=%s, reason=%s.",
            session.id,
            session.status.value,
            session.cycle_count,
            session.stop_reason,
        )
    except Exception:
        logger.exception("Agent session worker run failed.")


def main() -> None:
    init_db()
    run_worker_once()


if __name__ == "__main__":
    main()
