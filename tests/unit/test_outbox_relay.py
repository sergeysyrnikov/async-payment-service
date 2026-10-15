"""Unit tests for the outbox relay resilience."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

from app.core.config.rabbit import RabbitSettings
from app.infrastructure.messaging.rabbit.outbox_relay import OutboxRelay


class FakeUnitOfWorkContext:
    """Async context manager mimicking ``SqlAlchemyUnitOfWork``."""

    def __init__(self, uow: SimpleNamespace) -> None:
        self._uow = uow

    async def __aenter__(self) -> SimpleNamespace:
        return self._uow

    async def __aexit__(self, *exc_info: object) -> bool:
        return False


def make_relay(publisher: AsyncMock, logger: AsyncMock, poll_interval: float = 0.01) -> OutboxRelay:
    settings = RabbitSettings(outbox_poll_interval_sec=poll_interval)
    return OutboxRelay(db=object(), publisher=publisher, settings=settings, logger=logger)


def make_outbox_uow(messages: list[SimpleNamespace]) -> SimpleNamespace:
    """UoW mock whose outbox repository yields the messages only once."""

    async def fetch_unpublished(*args: object, **kwargs: object) -> list[SimpleNamespace]:
        result, messages[:] = messages[:], []
        return result

    return SimpleNamespace(
        outbox=SimpleNamespace(
            fetch_unpublished=fetch_unpublished,
            mark_published=AsyncMock(return_value=1),
        ),
    )


async def test_start_does_not_fail_when_broker_is_down(mocker) -> None:
    """The relay keeps retrying the connection instead of failing the API startup."""
    logger = AsyncMock()
    publisher = AsyncMock()
    publisher.start = AsyncMock(side_effect=ConnectionError("broker down"))
    relay = make_relay(publisher, logger)

    await relay.start()
    await asyncio.sleep(0.05)

    assert publisher.start.await_count >= 2
    assert logger.error.await_count >= 1
    await relay.stop()


async def test_publishes_outbox_messages_once_broker_is_available(mocker) -> None:
    """When the broker is reachable, outbox messages are published and marked."""
    logger = AsyncMock()
    publisher = AsyncMock()
    relay = make_relay(publisher, logger)

    message = SimpleNamespace(topic="payments.new", payload={"event": "payment.created"}, id=uuid4())
    uow = make_outbox_uow([message])
    mocker.patch(
        "app.infrastructure.messaging.rabbit.outbox_relay.SqlAlchemyUnitOfWork",
        lambda db: FakeUnitOfWorkContext(uow),
    )

    await relay.start()
    await asyncio.sleep(0.05)

    publisher.start.assert_awaited()
    publisher.publish.assert_awaited_once_with(
        routing_key="payments.new",
        payload={"event": "payment.created"},
    )
    uow.outbox.mark_published.assert_awaited_once_with(message_ids=[message.id])
    await relay.stop()


async def test_reconnects_after_publish_failure(mocker) -> None:
    """A failed publish resets the connection; the relay reconnects on the next loop."""
    logger = AsyncMock()
    publisher = AsyncMock()
    publisher.publish = AsyncMock(side_effect=RuntimeError("connection lost"))
    relay = make_relay(publisher, logger)

    message = SimpleNamespace(topic="payments.new", payload={}, id=uuid4())
    uow = SimpleNamespace(
        outbox=SimpleNamespace(
            fetch_unpublished=AsyncMock(return_value=[message]),
            mark_published=AsyncMock(return_value=0),
        ),
    )
    mocker.patch(
        "app.infrastructure.messaging.rabbit.outbox_relay.SqlAlchemyUnitOfWork",
        lambda db: FakeUnitOfWorkContext(uow),
    )

    await relay.start()
    await asyncio.sleep(0.05)

    assert publisher.start.await_count >= 2
    await relay.stop()
