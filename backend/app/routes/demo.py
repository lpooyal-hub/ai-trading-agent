from fastapi import APIRouter

from app.schemas import DemoSeedResponse, DemoStatusRead
from app.seed_demo_data import get_demo_status, seed_demo_data


router = APIRouter(prefix="/demo", tags=["demo"])


@router.get("/status", response_model=DemoStatusRead)
def get_status() -> DemoStatusRead:
    return DemoStatusRead(**get_demo_status())


@router.post("/seed", response_model=DemoSeedResponse)
def seed_demo() -> DemoSeedResponse:
    return DemoSeedResponse(**seed_demo_data())
