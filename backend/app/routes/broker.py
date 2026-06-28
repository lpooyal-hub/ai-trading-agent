from fastapi import APIRouter

from app.clients.toss_client import TossClient
from app.schemas import BrokerAccountPreviewRead, BrokerPositionPreviewRead, BrokerStatusRead
from app.services.broker_account_normalizer import BrokerAccountNormalizer
from app.services.broker_position_normalizer import BrokerPositionNormalizer


router = APIRouter(prefix="/broker", tags=["broker"])


@router.get("/status", response_model=BrokerStatusRead)
def get_broker_status() -> BrokerStatusRead:
    return BrokerStatusRead(**TossClient().get_status())


@router.get("/accounts")
def get_broker_accounts() -> dict:
    return TossClient().get_accounts()


@router.get("/accounts/normalized", response_model=BrokerAccountPreviewRead)
def get_normalized_broker_accounts() -> BrokerAccountPreviewRead:
    response = TossClient().get_accounts()
    accounts = []
    if response.get("success"):
        accounts = BrokerAccountNormalizer().normalize_accounts(response.get("data"))
    return BrokerAccountPreviewRead(
        success=bool(response.get("success")),
        status=str(response.get("status", "UNKNOWN")),
        http_status_code=response.get("http_status_code"),
        message=response.get("message"),
        accounts=accounts,
        raw_response_saved=bool(response.get("raw_response_saved", False)),
        cache_hit=bool(response.get("cache_hit", False)),
    )


@router.get("/positions")
def get_broker_positions() -> dict:
    return TossClient().get_positions()


@router.get("/positions/normalized", response_model=BrokerPositionPreviewRead)
def get_normalized_broker_positions() -> BrokerPositionPreviewRead:
    response = TossClient().get_positions()
    positions = []
    if response.get("success"):
        positions = BrokerPositionNormalizer().normalize_positions(response.get("data"))
    return BrokerPositionPreviewRead(
        success=bool(response.get("success")),
        status=str(response.get("status", "UNKNOWN")),
        http_status_code=response.get("http_status_code"),
        message=response.get("message"),
        positions=positions,
        raw_response_saved=bool(response.get("raw_response_saved", False)),
        cache_hit=bool(response.get("cache_hit", False)),
    )
