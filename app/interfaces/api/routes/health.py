from typing import Annotated

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends

from app.application.services.health_service import HealthService
from app.core.di.containers import Container

router = APIRouter(
    prefix="/health",
    tags=["health"],
)


@router.get("/")
@inject
async def health_check(
    health_service: Annotated[HealthService, Depends(Provide[Container.health_service])],
) -> dict[str, str]:
    """Check liveness of all infrastructure dependencies."""
    return await health_service.check()
