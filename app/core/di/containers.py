"""Dependency injection container."""

from dependency_injector import containers, providers

from app.application.services.health_service import HealthService
from app.application.services.payment_processor import PaymentProcessor
from app.application.services.payment_service import PaymentService
from app.core.config.database import DatabaseSettings
from app.core.config.processing import PaymentProcessingSettings
from app.core.config.rabbit import RabbitSettings
from app.core.config.security import SecuritySettings
from app.core.logging import setup_async_logging
from app.infrastructure.messaging.payment_gateway_emulator import PaymentGatewayEmulator
from app.infrastructure.messaging.rabbit.outbox_relay import OutboxRelay
from app.infrastructure.messaging.rabbit.payment_event_handler import PaymentEventHandler
from app.infrastructure.messaging.rabbit.publisher import RabbitEventPublisher
from app.infrastructure.messaging.rabbit.topology import build_broker
from app.infrastructure.messaging.webhook_sender import HttpWebhookSender
from app.infrastructure.persistence.database import DatabaseManager
from app.infrastructure.persistence.sqlalchemy_unit_of_work import SqlAlchemyUnitOfWork


class Container(containers.DeclarativeContainer):
    """Application DI container."""

    wiring_config = containers.WiringConfiguration(
        modules=[
            "app.interfaces.api.routes.health",
            "app.interfaces.api.routes.base",
            "app.interfaces.api.routes.payments",
            "app.interfaces.api.dependencies",
            "app.app",
        ],
    )

    config = providers.Configuration()

    # Core infrastructure
    db_settings = providers.Singleton(DatabaseSettings)

    db = providers.Singleton(DatabaseManager, db_settings=db_settings)

    logger = providers.Singleton(setup_async_logging)

    # Messaging / processing settings
    rabbit_settings = providers.Singleton(RabbitSettings)

    security_settings = providers.Singleton(SecuritySettings)

    processing_settings = providers.Singleton(PaymentProcessingSettings)

    # RabbitMQ
    rabbit_broker = providers.Singleton(build_broker, settings=rabbit_settings)

    event_publisher = providers.Singleton(
        RabbitEventPublisher,
        broker=rabbit_broker,
        settings=rabbit_settings,
        logger=logger,
    )

    # Unit of Work (a fresh instance per use-case call)
    uow = providers.Factory(SqlAlchemyUnitOfWork, db=db)

    # Services
    health_service = providers.Factory(
        HealthService,
        db=db,
    )

    payment_service = providers.Factory(
        PaymentService,
        uow=uow,
        event_routing_key=rabbit_settings.provided.payment_routing_key,
    )

    # Consumer-side components
    payment_gateway = providers.Factory(
        PaymentGatewayEmulator,
        settings=processing_settings,
        logger=logger,
    )

    webhook_sender = providers.Factory(
        HttpWebhookSender,
        settings=processing_settings,
        logger=logger,
    )

    payment_processor = providers.Factory(
        PaymentProcessor,
        uow=uow,
        gateway=payment_gateway,
        webhook_sender=webhook_sender,
        logger=logger,
    )

    payment_event_handler = providers.Factory(
        PaymentEventHandler,
        processor=payment_processor,
        broker=rabbit_broker,
        settings=rabbit_settings,
        logger=logger,
    )

    # Outbox relay (background task within the API process)
    outbox_relay = providers.Singleton(
        OutboxRelay,
        db=db,
        publisher=event_publisher,
        settings=rabbit_settings,
        logger=logger,
    )
