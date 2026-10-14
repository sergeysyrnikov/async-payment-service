"""RabbitMQ consumer-side handler with retry and DLQ orchestration."""

from __future__ import annotations

import asyncio
from typing import Any
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

    async def handle(self, *, message: dict[str, Any], msg: RabbitMessage) -> None:
        """Handle one message; manage retries and the dead letter queue."""
        try:
            await self._process(message)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            await self._handle_failure(message=message, msg=msg, exc=exc)
        else:
            await self._logger.info(
                "Payment event processed",
                extra={"component": "payment_event_handler", "payload": message},
            )

    async def _process(self, message: dict[str, Any]) -> None:
        """Dispatch the event payload to the payment processor."""
        payment_id = UUID(str(message.get("payment_id")))
        command = ProcessPaymentCommand(payment_id=payment_id)
        await self._processor.process_payment(command)

    async def _handle_failure(
        self,
        *,
        message: dict[str, Any],
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
                    "attempt": attempts,
                    "delay_sec": delay,
                },
                exc_info=exc,
            )
            await asyncio.sleep(delay)
            await self._broker.publish(
                message,
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
                "attempt": attempts,
                "payload": message,
            },
            exc_info=exc,
        )
        await msg.nack(requeue=False)
