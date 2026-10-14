"""RabbitMQ event publisher."""

from __future__ import annotations

from typing import Any

from aiologger import Logger  # type: ignore[import-untyped]
from faststream.rabbit import RabbitBroker, RabbitExchange

from app.core.config.rabbit import RabbitSettings
from app.domain.interfaces.messaging.event_publisher import IEventPublisher
from app.infrastructure.messaging.rabbit.topology import build_payment_exchange


class RabbitEventPublisher(IEventPublisher):
    """Publishes integration events to the main payment exchange."""

    def __init__(
        self,
        *,
        broker: RabbitBroker,
        settings: RabbitSettings,
        logger: Logger,
    ) -> None:
        self._broker = broker
        self._settings = settings
        self._logger = logger
        self._exchange: RabbitExchange = build_payment_exchange(settings)

    async def start(self) -> None:
        """Connect the broker for publishing."""
        await self._broker.connect()
        await self._logger.info("RabbitMQ publisher connected")

    async def stop(self) -> None:
        """Close the broker connection."""
        await self._broker.close()
        await self._logger.info("RabbitMQ publisher closed")

    async def publish(
        self,
        *,
        routing_key: str,
        payload: dict[str, Any],
        headers: dict[str, Any] | None = None,
    ) -> None:
        """Publish an event payload to the given routing key."""
        await self._broker.publish(
            payload,
            exchange=self._exchange,
            routing_key=routing_key,
            headers=headers,
        )
