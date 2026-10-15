"""RabbitMQ consumer entrypoint.

Run with: ``uv run python -m app.consumer``

Подписчики объявлены на уровне модуля: pydantic v2 не может пересобрать
валидационную модель fast_depends для функций, объявленных внутри другой
функции (PydanticUserError: ``<func> is not fully defined``).
"""

import asyncio

from faststream import Context, FastStream
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

_broker: RabbitBroker = container.rabbit_broker()
_handler = container.payment_event_handler()
_logger = container.logger()
_settings = container.rabbit_settings()

_payment_queue = build_payment_queue(_settings)
_payment_exchange = build_payment_exchange(_settings)
_dead_letter_queue = build_dead_letter_queue(_settings)
_dead_letter_exchange = build_dead_letter_exchange(_settings)


@_broker.subscriber(_payment_queue, _payment_exchange)
async def payment_event(
    event: str,
    payment_id: str,
    msg: RabbitMessage = Context("message"),
) -> None:
    # body-поля распаковываются в kwargs по ключам; сырое сообщение — через Context("message")
    await _handler.handle(event=event, payment_id=payment_id, msg=msg)


@_broker.subscriber(_dead_letter_queue, _dead_letter_exchange)
async def dead_letter(
    event: str,
    payment_id: str,
    msg: RabbitMessage = Context("message"),
) -> None:
    await _logger.error(
        "Message moved to the dead letter queue",
        extra={"component": "consumer", "event": event, "payment_id": payment_id, "headers": dict(msg.headers)},
    )


def build_consumer() -> FastStream:
    """Return the ready-to-run consumer application."""
    return FastStream(_broker)


def main() -> None:
    """Run the RabbitMQ consumer until stopped."""
    consumer_app = build_consumer()
    asyncio.run(consumer_app.run())


if __name__ == "__main__":
    main()
