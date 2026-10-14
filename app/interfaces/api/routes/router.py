from fastapi import APIRouter, Depends

from app.interfaces.api.dependencies import require_api_key
from app.interfaces.api.routes.base import root_router
from app.interfaces.api.routes.health import router as health_router
from app.interfaces.api.routes.payments import router as payments_router

# Create main router with version prefix; static API key auth for all endpoints
main_router = APIRouter(
    prefix="/api/v1",
    dependencies=[Depends(require_api_key)],
)

# Include routers
main_router.include_router(health_router)
main_router.include_router(payments_router)
main_router.include_router(root_router)
