"""Unit tests for PaymentProcessor."""

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.application.commands.payment_commands import ProcessPaymentCommand
from app.application.services.payment_processor import PaymentProcessor
from app.domain.exceptions import ExternalServiceError
from app.domain.models.payment import Currency, GatewayResult, Payment, PaymentStatus


def make_payment(**overrides) -> Payment:
    """Build a pending payment for the processor."""
    defaults = dict(
        amount=Decimal("100.50"),
        currency=Currency.RUB,
        idempotency_key="key-1",
        webhook_url="https://example.com/webhook",
        status=PaymentStatus.PENDING,
        id=uuid4(),
        created_at=datetime.now(timezone.utc),
    )
    defaults.update(overrides)
    return Payment(**defaults)


@pytest.fixture
def mock_logger():
    logger = AsyncMock()
    logger.info = AsyncMock()
    logger.warning = AsyncMock()
    logger.error = AsyncMock()
    return logger


@pytest.fixture
def mock_uow(mocker):
    uow = mocker.MagicMock()
    uow.__aenter__ = mocker.AsyncMock(return_value=uow)
    uow.__aexit__ = mocker.AsyncMock(return_value=None)
    uow.payments = mocker.MagicMock()
    uow.payments.get_for_update = mocker.AsyncMock(return_value=make_payment())
    uow.payments.update_status = mocker.AsyncMock(
        side_effect=lambda **kwargs: make_payment(
            status=kwargs["status"],
            failure_reason=kwargs["failure_reason"],
            processed_at=datetime.now(timezone.utc),
        ),
    )
    return uow


@pytest.fixture
def mock_gateway():
    gateway = AsyncMock()
    gateway.process = AsyncMock(return_value=GatewayResult(success=True))
    return gateway


@pytest.fixture
def mock_webhook_sender():
    sender = AsyncMock()
    sender.send = AsyncMock()
    return sender


@pytest.fixture
def processor(mock_uow, mock_gateway, mock_webhook_sender, mock_logger):
    return PaymentProcessor(
        uow=mock_uow,
        gateway=mock_gateway,
        webhook_sender=mock_webhook_sender,
        logger=mock_logger,
    )


@pytest.mark.asyncio
async def test_process_payment_success(processor, mock_uow, mock_gateway, mock_webhook_sender):
    """Successful gateway charge: status SUCCEEDED, no failure reason, webhook sent."""
    payment_id = uuid4()
    await processor.process_payment(ProcessPaymentCommand(payment_id=payment_id))

    mock_uow.payments.get_for_update.assert_awaited_once_with(payment_id=payment_id)
    mock_gateway.process.assert_awaited_once()
    mock_uow.payments.update_status.assert_awaited_once()
    kwargs = mock_uow.payments.update_status.await_args.kwargs
    assert kwargs["status"] is PaymentStatus.SUCCEEDED
    assert kwargs["failure_reason"] is None
    mock_webhook_sender.send.assert_awaited_once()
    assert mock_webhook_sender.send.await_args.kwargs["url"] == "https://example.com/webhook"


@pytest.mark.asyncio
async def test_process_payment_gateway_decline(processor, mock_uow, mock_gateway, mock_webhook_sender):
    """Declined gateway charge: status FAILED with reason, webhook still sent."""
    mock_gateway.process = AsyncMock(return_value=GatewayResult(success=False, reason="Payment gateway declined"))

    await processor.process_payment(ProcessPaymentCommand(payment_id=uuid4()))

    kwargs = mock_uow.payments.update_status.await_args.kwargs
    assert kwargs["status"] is PaymentStatus.FAILED
    assert kwargs["failure_reason"] == "Payment gateway declined"
    mock_webhook_sender.send.assert_awaited_once()


@pytest.mark.asyncio
async def test_process_payment_non_positive_amount_fails_gracefully(
    processor, mock_uow, mock_gateway, mock_webhook_sender, mock_logger
):
    """A non-positive amount (going below zero) marks the payment failed instead of raising."""
    mock_uow.payments.get_for_update = AsyncMock(return_value=make_payment(amount=Decimal("-10.00")))

    await processor.process_payment(ProcessPaymentCommand(payment_id=uuid4()))

    mock_gateway.process.assert_not_awaited()
    kwargs = mock_uow.payments.update_status.await_args.kwargs
    assert kwargs["status"] is PaymentStatus.FAILED
    assert kwargs["failure_reason"] == "Payment amount must be positive"
    mock_webhook_sender.send.assert_awaited_once()
    mock_logger.warning.assert_awaited()


@pytest.mark.asyncio
async def test_process_payment_skips_missing_payment(processor, mock_uow, mock_gateway, mock_webhook_sender):
    """Missing payment row: message skipped without updates or webhook."""
    mock_uow.payments.get_for_update = AsyncMock(return_value=None)

    await processor.process_payment(ProcessPaymentCommand(payment_id=uuid4()))

    mock_uow.payments.update_status.assert_not_awaited()
    mock_gateway.process.assert_not_awaited()
    mock_webhook_sender.send.assert_not_awaited()


@pytest.mark.asyncio
async def test_process_payment_skips_already_processed(processor, mock_uow, mock_gateway, mock_webhook_sender):
    """Non-pending payment (already processed): idempotent skip."""
    mock_uow.payments.get_for_update = AsyncMock(
        return_value=make_payment(status=PaymentStatus.SUCCEEDED),
    )

    await processor.process_payment(ProcessPaymentCommand(payment_id=uuid4()))

    mock_gateway.process.assert_not_awaited()
    mock_uow.payments.update_status.assert_not_awaited()
    mock_webhook_sender.send.assert_not_awaited()


@pytest.mark.asyncio
async def test_process_payment_webhook_failure_is_logged(processor, mock_webhook_sender, mock_logger):
    """Webhook delivery failure after retries: logged, not raised."""
    mock_webhook_sender.send = AsyncMock(side_effect=ExternalServiceError("webhook", "boom"))

    await processor.process_payment(ProcessPaymentCommand(payment_id=uuid4()))  # no exception

    mock_logger.error.assert_awaited()


@pytest.mark.asyncio
async def test_process_payment_uses_row_lock(processor, mock_uow):
    """The payment row is fetched via get_for_update (SELECT ... FOR UPDATE) before processing."""
    payment_id = uuid4()

    await processor.process_payment(ProcessPaymentCommand(payment_id=payment_id))

    mock_uow.payments.get_for_update.assert_awaited_once_with(payment_id=payment_id)
