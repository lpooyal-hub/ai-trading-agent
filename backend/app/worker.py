import time
from collections.abc import Callable

from app.config import Settings, get_settings
from app.database import SessionLocal, init_db
from app.services.agent_graph_service import AgentGraphService
from app.utils.logger import get_logger
from app.utils.market_hours import is_market_open


logger = get_logger(__name__)
MARKET_POLL_SECONDS = 60.0


def worker_can_start_session(settings: Settings) -> bool:
    """Keep the worker inert unless automation is explicitly enabled and the market is open."""
    return bool(settings.agent_scheduler_enabled and is_market_open(settings))


def wait_until_session_start(
    settings: Settings,
    *,
    poll_seconds: float = MARKET_POLL_SECONDS,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> None:
    delay = max(float(poll_seconds), 1.0)
    while not worker_can_start_session(settings):
        sleep_fn(delay)


def wait_until_market_close(
    settings: Settings,
    *,
    poll_seconds: float = MARKET_POLL_SECONDS,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> None:
    """Prevent an early-ended session from restarting during the same market day."""
    delay = max(float(poll_seconds), 1.0)
    while is_market_open(settings):
        sleep_fn(delay)


def run_agent_session(graph_service: AgentGraphService):
    with SessionLocal() as db:
        return graph_service.run_session(db, trigger_source="worker")


def run_worker(
    settings: Settings | None = None,
    *,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> None:
    worker_settings = settings or get_settings()
    graph_service = AgentGraphService()

    logger.info(
        "Agent session worker started (scheduler_enabled=%s, market_timezone=%s).",
        worker_settings.agent_scheduler_enabled,
        worker_settings.agent_market_timezone,
    )

    while True:
        wait_until_session_start(worker_settings, sleep_fn=sleep_fn)
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

        wait_until_market_close(worker_settings, sleep_fn=sleep_fn)


def main() -> None:
    init_db()
    run_worker()


if __name__ == "__main__":
    main()
