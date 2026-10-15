"""RabbitMQ consumer-side handler with retry and DLQ orchestration."""

from __future__ import annotations

import asyncio
from uuid import UUID

from aiologger import Logger  # type: ignore[import-untyped]
from faststream.rabbit import RabbitBroker
from faststream.rabbit.message import RabbitMessage

from app.application.commands.payment_commands import ProcessPaymentCommand
from app.application.services.payment_processor import PaymentProcessor
from app.core.config.rabbit import RabbitSettings
from app.infrastructure.messaging.rabbit.topology import build_payment_exchange, build_payment_queue

RETRY_HEADER = "x-retry-count"


class PaymentEventHandler:
    """Processes payment events: on failure retries with exponential backoff, then DLQ."""

    def __init__(
        self,
        *,
        processor: PaymentProcessor,
        broker: RabbitBroker,
        settings: RabbitSettings,
        logger: Logger,
    ) -> None:
        self._processor = processor
        self._broker = broker
        self._settings = settings
        self._logger = logger
        self._queue = build_payment_queue(settings)
        self._exchange = build_payment_exchange(settings)

    async def handle(self, *, event: str, payment_id: str, msg: RabbitMessage) -> None:
        """Handle one message; manage retries and the dead letter queue."""
        try:
            await self._process(payment_id)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            await self._handle_failure(event=event, payment_id=payment_id, msg=msg, exc=exc)
        else:
            await self._logger.info(
                "Payment event processed",
                extra={"component": "payment_event_handler", "event": event, "payment_id": payment_id},
            )

    async def _process(self, payment_id: str) -> None:
        """Dispatch the event to the payment processor."""
        command = ProcessPaymentCommand(payment_id=UUID(payment_id))
        await self._processor.process_payment(command)

    async def _handle_failure(
        self,
        *,
        event: str,
        payment_id: str,
        msg: RabbitMessage,
        exc: Exception,
    ) -> None:
        """Retry with exponential delay or move the message to the DLQ."""
        attempts = int(msg.headers.get(RETRY_HEADER) or 0) + 1

        if attempts < self._settings.max_attempts:
            delay = self._settings.retry_base_delay_sec * (2 ** (attempts - 1))
            await self._logger.warning(
                "Payment event processing failed, retrying",
                extra={
                    "component": "payment_event_handler",
                    "payment_id": payment_id,
                    "attempt": attempts,
                    "delay_sec": delay,
                },
                exc_info=exc,
            )
            await asyncio.sleep(delay)
            await self._broker.publish(
                {"event": event, "payment_id": payment_id},
                queue=self._queue,
                exchange=self._exchange,
                routing_key=self._settings.payment_routing_key,
                headers={RETRY_HEADER: attempts},
            )
            await msg.ack()
            return

        await self._logger.error(
            "Payment event failed after max attempts, moving to DLQ",
            extra={
                "component": "payment_event_handler",
                "payment_id": payment_id,
                "attempt": attempts,
                "event": event,
            },
            exc_info=exc,
        )
        await msg.nack(requeue=False)
