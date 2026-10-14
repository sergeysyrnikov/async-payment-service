"""Outbox relay: publishes persisted outbox messages to RabbitMQ."""

from __future__ import annotations

import asyncio
from uuid import UUID

from aiologger import Logger  # type: ignore[import-untyped]

from app.core.config.rabbit import RabbitSettings
from app.domain.interfaces.messaging.event_publisher import IEventPublisher
from app.infrastructure.persistence.database import DatabaseManager
from app.infrastructure.persistence.sqlalchemy_unit_of_work import SqlAlchemyUnitOfWork


class OutboxRelay:
    """Background task: poll the outbox table and publish events to the broker.

    Delivery guarantee (at-least-once): a message is marked as published only
    after a successful broker publish, within the same DB transaction. A crash
    between publish and mark leads to a republish — consumers are idempotent.
    """

    def __init__(
        self,
        *,
        db: DatabaseManager,
        publisher: IEventPublisher,
        settings: RabbitSettings,
        logger: Logger,
    ) -> None:
        self._db = db
        self._publisher = publisher
        self._settings = settings
        self._logger = logger
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        """Connect the publisher and start the polling loop."""
        if self._task is not None:
            return
        await self._publisher.start()
        self._task = asyncio.create_task(self._run(), name="outbox-relay")
        await self._logger.info("Outbox relay started")

    async def stop(self) -> None:
        """Cancel the polling loop and close the publisher."""
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None
        await self._publisher.stop()
        await self._logger.info("Outbox relay stopped")

    async def _run(self) -> None:
        """Poll the outbox forever; sleep only when there is nothing to publish."""
        while True:
            published = 0
            try:
                published = await self._relay_once()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                await self._logger.error(
                    "Outbox relay iteration failed",
                    extra={"component": "outbox_relay"},
                    exc_info=exc,
                )
            if published == 0:
                await asyncio.sleep(self._settings.outbox_poll_interval_sec)

    async def _relay_once(self) -> int:
        """Publish one batch of unpublished outbox messages; returns the batch size."""
        async with SqlAlchemyUnitOfWork(self._db) as uow:
            messages = await uow.outbox.fetch_unpublished(limit=self._settings.outbox_batch_size)
            if not messages:
                return 0

            for message in messages:
                await self._publisher.publish(
                    routing_key=message.topic,
                    payload=message.payload,
                )
                await self._logger.info(
                    "Outbox message published",
                    extra={
                        "component": "outbox_relay",
                        "outbox_message_id": str(message.id),
                        "routing_key": message.topic,
                    },
                )

            message_ids: list[UUID] = [message.id for message in messages if message.id is not None]
            await uow.outbox.mark_published(message_ids=message_ids)
            return len(messages)
