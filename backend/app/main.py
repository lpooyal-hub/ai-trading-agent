from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import init_db
from app.routes import (
    agent,
    broker,
    demo,
    decisions,
    evaluations,
    health,
    llm_usage,
    market,
    orders,
    portfolio,
    settings,
)
from app.utils.logger import get_logger


app_settings = get_settings()
logger = get_logger(__name__)

app = FastAPI(title=app_settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=app_settings.cors_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    if app_settings.dry_run:
        logger.warning("Running in DRY_RUN mode. Real order execution is disabled.")
    if not app_settings.live_trading_enabled:
        logger.warning("Live trading is disabled by configuration.")
    if app_settings.use_mock_data:
        logger.warning("Using mock data. No real brokerage or OpenAI API calls will be made.")
    init_db()


app.include_router(health.router)
app.include_router(settings.router)
app.include_router(portfolio.router)
app.include_router(agent.router)
app.include_router(broker.router)
app.include_router(demo.router)
app.include_router(decisions.router)
app.include_router(orders.router)
app.include_router(evaluations.router)
app.include_router(llm_usage.router)
app.include_router(market.router)
