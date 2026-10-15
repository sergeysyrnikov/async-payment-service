"""Unit tests for PaymentEventHandler (retry / DLQ orchestration)."""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.application.services.payment_processor import PaymentProcessor
from app.core.config.rabbit import RabbitSettings
from app.infrastructure.messaging.rabbit.payment_event_handler import RETRY_HEADER, PaymentEventHandler


@pytest.fixture
def settings() -> RabbitSettings:
    return RabbitSettings(
        max_attempts=3,
        retry_base_delay_sec=1.0,
    )


@pytest.fixture
def mock_processor():
    processor = AsyncMock(spec=PaymentProcessor)
    processor.process_payment = AsyncMock()
    return processor


@pytest.fixture
def mock_broker():
    broker = AsyncMock()
    broker.publish = AsyncMock()
    return broker


@pytest.fixture
def mock_logger():
    logger = AsyncMock()
    logger.info = AsyncMock()
    logger.warning = AsyncMock()
    logger.error = AsyncMock()
    return logger


@pytest.fixture
def make_msg():
    def _make(headers: dict | None = None) -> MagicMock:
        msg = MagicMock()
        msg.headers = headers or {}
        msg.ack = AsyncMock()
        msg.nack = AsyncMock()
        return msg

    return _make


@pytest.fixture
def handler(mock_processor, mock_broker, settings, mock_logger):
    return PaymentEventHandler(
        processor=mock_processor,
        broker=mock_broker,
        settings=settings,
        logger=mock_logger,
    )


@pytest.mark.asyncio
async def test_success_processes_and_no_retry(handler, mock_processor, mock_broker, make_msg):
    """Successful processing: no retry, no nack."""
    msg = make_msg()

    await handler.handle(event="payment.created", payment_id=str(uuid4()), msg=msg)

    mock_processor.process_payment.assert_awaited_once()
    mock_broker.publish.assert_not_awaited()
    msg.nack.assert_not_awaited()


@pytest.mark.asyncio
async def test_failure_republishes_with_retry_header(handler, mock_processor, mock_broker, make_msg, mocker):
    """First failure: exponential delay, republish with x-retry-count, ack the original."""
    mock_processor.process_payment = AsyncMock(side_effect=ValueError("boom"))
    sleep = mocker.patch("app.infrastructure.messaging.rabbit.payment_event_handler.asyncio.sleep", AsyncMock())
    msg = make_msg(headers={})

    await handler.handle(event="payment.created", payment_id=str(uuid4()), msg=msg)

    sleep.assert_awaited_once_with(1.0)
    mock_broker.publish.assert_awaited_once()
    kwargs = mock_broker.publish.await_args.kwargs
    assert kwargs["headers"] == {RETRY_HEADER: 1}
    msg.ack.assert_awaited_once()
    msg.nack.assert_not_awaited()


@pytest.mark.asyncio
async def test_failure_after_max_attempts_goes_to_dlq(handler, mock_processor, mock_broker, make_msg, mocker):
    """Third failure (attempts >= max): nack without requeue -> routed to the DLQ."""
    mock_processor.process_payment = AsyncMock(side_effect=ValueError("boom"))
    sleep = mocker.patch("app.infrastructure.messaging.rabbit.payment_event_handler.asyncio.sleep", AsyncMock())
    msg = make_msg(headers={RETRY_HEADER: 2})

    await handler.handle(event="payment.created", payment_id=str(uuid4()), msg=msg)

    sleep.assert_not_awaited()
    mock_broker.publish.assert_not_awaited()
    msg.nack.assert_awaited_once_with(requeue=False)
    msg.ack.assert_not_awaited()


@pytest.mark.asyncio
async def test_retry_delay_grows_exponentially(handler, mock_processor, mock_broker, make_msg, mocker):
    """Second attempt delay is base * 2**1."""
    mock_processor.process_payment = AsyncMock(side_effect=ValueError("boom"))
    sleep = mocker.patch("app.infrastructure.messaging.rabbit.payment_event_handler.asyncio.sleep", AsyncMock())
    msg = make_msg(headers={RETRY_HEADER: 1})

    await handler.handle(event="payment.created", payment_id=str(uuid4()), msg=msg)

    sleep.assert_awaited_once_with(2.0)
    kwargs = mock_broker.publish.await_args.kwargs
    assert kwargs["headers"] == {RETRY_HEADER: 2}
