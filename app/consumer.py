"""RabbitMQ consumer entrypoint.

Run with: ``uv run python -m app.consumer``
"""

from __future__ import annotations

import asyncio
from typing import Any

from faststream import FastStream
from faststream.rabbit import RabbitBroker
from faststream.rabbit.message import RabbitMessage

from app.core.di.containers import Container
from app.infrastructure.messaging.rabbit.topology import (
    build_dead_letter_exchange,
    build_dead_letter_queue,
    build_payment_exchange,
    build_payment_queue,
)

container = Container()


def build_consumer() -> FastStream:
    """Wire subscribers to the broker and return the ready-to-run application."""
    broker: RabbitBroker = container.rabbit_broker()
    settings = container.rabbit_settings()
    logger = container.logger()
    handler = container.payment_event_handler()

    payment_queue = build_payment_queue(settings)
    payment_exchange = build_payment_exchange(settings)
    dead_letter_queue = build_dead_letter_queue(settings)
    dead_letter_exchange = build_dead_letter_exchange(settings)

    @broker.subscriber(payment_queue, payment_exchange)
    async def payment_event(message: dict[str, Any], msg: RabbitMessage) -> None:
        await handler.handle(message=message, msg=msg)

    @broker.subscriber(dead_letter_queue, dead_letter_exchange)
    async def dead_letter(message: dict[str, Any], msg: RabbitMessage) -> None:
        await logger.error(
            "Message moved to the dead letter queue",
            extra={"component": "consumer", "payload": message, "headers": dict(msg.headers)},
        )

    return FastStream(broker)


def main() -> None:
    """Run the RabbitMQ consumer until stopped."""
    consumer_app = build_consumer()
    asyncio.run(consumer_app.run())


if __name__ == "__main__":
    main()
