"""RabbitMQ topology: exchanges, queues and the broker factory."""

from __future__ import annotations

from faststream.rabbit import ExchangeType, RabbitBroker, RabbitExchange, RabbitQueue
from faststream.rabbit.schemas.queue import ClassicQueueArgs

from app.core.config.rabbit import RabbitSettings


def build_payment_exchange(settings: RabbitSettings) -> RabbitExchange:
    """Main direct exchange for payment events."""
    return RabbitExchange(
        settings.exchange,
        type=ExchangeType.DIRECT,
        durable=True,
    )


def build_payment_queue(settings: RabbitSettings) -> RabbitQueue:
    """Queue for new payment events; dead messages are routed to the DLQ via DLX."""
    return RabbitQueue(
        settings.payment_queue,
        durable=True,
        routing_key=settings.payment_routing_key,
        arguments=ClassicQueueArgs(
            **{
                "x-dead-letter-exchange": settings.dead_letter_exchange,
                "x-dead-letter-routing-key": settings.dead_letter_routing_key,
            },
        ),
    )


def build_dead_letter_exchange(settings: RabbitSettings) -> RabbitExchange:
    """Exchange messages fall onto after exhausting retries (DLX)."""
    return RabbitExchange(
        settings.dead_letter_exchange,
        type=ExchangeType.DIRECT,
        durable=True,
    )


def build_dead_letter_queue(settings: RabbitSettings) -> RabbitQueue:
    """Dead letter queue for messages not processed after all attempts."""
    return RabbitQueue(
        settings.dead_letter_queue,
        durable=True,
        routing_key=settings.dead_letter_routing_key,
    )


def build_broker(settings: RabbitSettings) -> RabbitBroker:
    """Create a RabbitMQ broker instance (not connected)."""
    return RabbitBroker(
        url=settings.url,
    )
