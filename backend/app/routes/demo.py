from fastapi import APIRouter, Depends, HTTPException

from app.config import get_settings
from app.schemas import DemoSeedResponse, DemoStatusRead
from app.security import require_admin_api_key
from app.seed_demo_data import get_demo_status, seed_demo_data


router = APIRouter(prefix="/demo", tags=["demo"])


@router.get("/status", response_model=DemoStatusRead)
def get_status() -> DemoStatusRead:
    settings = get_settings()
    return DemoStatusRead(
        **get_demo_status(),
        demo_enabled=settings.demo_mode_enabled,
        demo_reason=settings.demo_mode_reason,
    )


@router.post("/seed", response_model=DemoSeedResponse, dependencies=[Depends(require_admin_api_key)])
def seed_demo() -> DemoSeedResponse:
    settings = get_settings()
    if not settings.demo_mode_enabled:
        raise HTTPException(status_code=403, detail=settings.demo_mode_reason)

    return DemoSeedResponse(
        **seed_demo_data(),
        demo_enabled=settings.demo_mode_enabled,
        demo_reason=settings.demo_mode_reason,
    )
