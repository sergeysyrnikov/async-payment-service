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

    The API process starts even when RabbitMQ is unavailable: the relay
    connects lazily and keeps retrying in the polling loop, so outbox events
    accumulate in the database and are published once the broker is back.
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
        self._connected = False
        self._failure_count = 0

    async def start(self) -> None:
        """Start the polling loop without blocking on broker availability."""
        if self._task is not None:
            return
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
        try:
            await self._publisher.stop()
        except Exception as exc:  # the broker may have never been connected
            await self._logger.warning(
                "Outbox publisher shutdown error",
                extra={"component": "outbox_relay"},
                exc_info=exc,
            )
        self._connected = False
        self._failure_count = 0
        await self._logger.info("Outbox relay stopped")

    async def _run(self) -> None:
        """Poll the outbox forever; sleep only when there is nothing to publish."""
        while True:
            published = await self._step()
            if published == 0:
                await asyncio.sleep(self._settings.outbox_poll_interval_sec)

    async def _step(self) -> int:
        """One relay iteration: reconnect if needed and try to publish a batch."""
        try:
            await self._ensure_publisher()
            return await self._relay_once()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            await self._log_failure(exc)
            return 0

    async def _ensure_publisher(self) -> None:
        """Connect the publisher once; reconnection retries happen in the loop."""
        if not self._connected:
            await self._publisher.start()
            if self._failure_count:
                await self._logger.info(
                    "RabbitMQ connection restored",
                    extra={"component": "outbox_relay", "retries": self._failure_count},
                )
            self._failure_count = 0
            self._connected = True

    async def _log_failure(self, exc: Exception) -> None:
        """Log broker failures without spamming a full traceback every second."""
        was_connected = self._connected
        self._connected = False
        self._failure_count += 1
        if was_connected:
            await self._logger.error(
                "Outbox relay lost RabbitMQ connection",
                extra={"component": "outbox_relay"},
                exc_info=exc,
            )
        elif self._failure_count == 1:
            await self._logger.error(
                "RabbitMQ is unreachable; outbox events are buffered until the broker is back",
                extra={"component": "outbox_relay", "error": str(exc)},
            )
        elif self._failure_count % 30 == 0:
            await self._logger.warning(
                "RabbitMQ is still unreachable; outbox events remain buffered",
                extra={
                    "component": "outbox_relay",
                    "retries": self._failure_count,
                    "error": str(exc),
                },
            )

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
