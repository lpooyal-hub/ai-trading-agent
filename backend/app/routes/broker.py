from fastapi import APIRouter

from app.clients.toss_client import TossClient
from app.schemas import BrokerStatusRead


router = APIRouter(prefix="/broker", tags=["broker"])


@router.get("/status", response_model=BrokerStatusRead)
def get_broker_status() -> BrokerStatusRead:
    return BrokerStatusRead(**TossClient().get_status())


@router.get("/accounts")
def get_broker_accounts() -> dict:
    return TossClient().get_accounts()


@router.get("/positions")
def get_broker_positions() -> dict:
    return TossClient().get_positions()
