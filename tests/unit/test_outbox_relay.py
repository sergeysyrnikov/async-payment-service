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
    # ровно одна запись на переход в состояние "брокер недоступен" — без спама
    assert logger.error.await_count == 1
    assert logger.warning.await_count == 0
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


async def test_failure_counter_resets_after_restore(mocker) -> None:
    """A restored connection resets the failure counter: every outage counts fresh."""
    logger = AsyncMock()
    publisher = AsyncMock()
    # outage 1: broker unreachable (start fails x3) -> restored;
    # then the established connection breaks on publish -> next connect also fails
    # (same outage, counter keeps growing) -> broker is back -> restored with 2, not 5.
    start_effects = [ConnectionError("down")] * 3 + [None] + [ConnectionError("down")] + [None] * 20
    publisher.start = AsyncMock(side_effect=start_effects)
    publisher.publish = AsyncMock(side_effect=[RuntimeError("lost")] + [None] * 20)
    relay = make_relay(publisher, logger)

    message = SimpleNamespace(topic="payments.new", payload={}, id=uuid4())
    delivered = {"done": False}

    async def fetch_unpublished(*args: object, **kwargs: object) -> list[SimpleNamespace]:
        return [] if delivered["done"] else [message]

    async def mark_published(*, message_ids: list[object]) -> int:
        delivered["done"] = True
        return 1

    uow = SimpleNamespace(
        outbox=SimpleNamespace(fetch_unpublished=fetch_unpublished, mark_published=mark_published),
    )
    mocker.patch(
        "app.infrastructure.messaging.rabbit.outbox_relay.SqlAlchemyUnitOfWork",
        lambda db: FakeUnitOfWorkContext(uow),
    )

    for _ in range(3):  # outage 1: connect fails, counts 1..3
        assert await relay._step() == 0
    assert await relay._step() == 0  # connected ("restored: 3"), publish fails -> "lost connection", count=1
    assert await relay._step() == 0  # connect fails again (same outage, count=2, silent)
    assert await relay._step() == 1  # connected ("restored: 2"), publish succeeds

    restored = [
        call.kwargs["extra"]["retries"]
        for call in logger.info.await_args_list
        if call.kwargs.get("extra", {}).get("retries")
    ]
    # без обнуления на строке 95 второй restore показал бы накопленные 4, а не 2
    assert restored == [3, 2]
    # outage 1 -> "unreachable", разрыв установленного соединения -> "lost connection"
    assert logger.error.await_count == 2
