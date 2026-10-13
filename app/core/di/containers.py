"""Dependency injection container."""

from dependency_injector import containers, providers

from app.application.services.health_service import HealthService
from app.core.config.database import DatabaseSettings
from app.core.logging import setup_async_logging
from app.infrastructure.persistence.database import DatabaseManager


class Container(containers.DeclarativeContainer):
    """Application DI container."""

    wiring_config = containers.WiringConfiguration(
        modules=[
            "app.interfaces.api.routes.health",
            "app.interfaces.api.routes.base",
            "app.app",
        ],
    )

    config = providers.Configuration()

    # Core infrastructure
    db_settings = providers.Singleton(DatabaseSettings)

    db = providers.Singleton(DatabaseManager, db_settings=db_settings)

    logger = providers.Singleton(setup_async_logging)

    # Services
    health_service = providers.Factory(
        HealthService,
        db=db,
    )
