"""Unit tests for PaymentService."""

from datetime import datetime, timezone
from decimal import Decimal
from types import TracebackType
from uuid import uuid4

import pytest

from app.application.commands.payment_commands import CreatePaymentCommand
from app.application.services.payment_service import PaymentService
from app.domain.exceptions import DuplicateIdempotencyKeyError, EntityNotFoundError
from app.domain.models.payment import Currency, Payment, PaymentStatus


class FakeUow:
    """Test double for IUnitOfWork recording usage."""

    def __init__(self, payments, outbox) -> None:
        self.payments = payments
        self.outbox = outbox
        self.entered = 0
        self.exc_types: list[object | None] = []

    async def __aenter__(self) -> "FakeUow":
        self.entered += 1
        return self

    async def __aexit__(
        self,
        exc_type: object,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.exc_types.append(exc_type)


def make_payment(**overrides) -> Payment:
    """Build a persisted payment for assertions."""
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


def make_command() -> CreatePaymentCommand:
    """Build a create payment command."""
    return CreatePaymentCommand(
        amount=Decimal("100.50"),
        currency=Currency.RUB,
        idempotency_key="key-1",
        webhook_url="https://example.com/webhook",
        description="Test payment",
        metadata={"order_id": "42"},
    )


@pytest.mark.asyncio
async def test_create_payment_saves_payment_and_outbox_event(mocker):
    """New payment: payment + outbox message saved in the same UoW transaction."""
    payments = mocker.MagicMock()
    payments.get_by_idempotency_key = mocker.AsyncMock(return_value=None)
    saved_id = uuid4()
    payments.save = mocker.AsyncMock(return_value=saved_id)
    payments.get_by_id = mocker.AsyncMock(
        return_value=make_payment(id=saved_id, idempotency_key="key-1"),
    )
    outbox = mocker.MagicMock()
    outbox.save = mocker.AsyncMock(return_value=uuid4())

    uow = FakeUow(payments=payments, outbox=outbox)
    service = PaymentService(uow=uow, event_routing_key="payments.new")

    created = await service.create_payment(make_command())

    assert created.id == saved_id
    assert created.status is PaymentStatus.PENDING
    payments.save.assert_awaited_once()
    outbox.save.assert_awaited_once()
    saved_outbox = outbox.save.await_args.args[0]
    assert saved_outbox.topic == "payments.new"
    assert saved_outbox.payload["event"] == "payment.created"
    assert saved_outbox.payload["payment_id"] == str(saved_id)
    # UoW exit без исключения (commit path)
    assert uow.exc_types == [None, None]


@pytest.mark.asyncio
async def test_create_payment_returns_existing_for_repeated_key(mocker):
    """Repeated idempotency key returns the existing payment without saving."""
    existing = make_payment()
    payments = mocker.MagicMock()
    payments.get_by_idempotency_key = mocker.AsyncMock(return_value=existing)
    payments.save = mocker.AsyncMock()
    outbox = mocker.MagicMock()
    outbox.save = mocker.AsyncMock()

    service = PaymentService(uow=FakeUow(payments=payments, outbox=outbox), event_routing_key="payments.new")

    result = await service.create_payment(make_command())

    assert result is existing
    payments.save.assert_not_awaited()
    outbox.save.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_payment_handles_unique_race(mocker):
    """Concurrent duplicate save (IntegrityError -> DuplicateIdempotencyKeyError) re-fetches existing."""
    existing = make_payment()
    payments = mocker.MagicMock()
    payments.get_by_idempotency_key = mocker.AsyncMock(side_effect=[None, existing])
    payments.save = mocker.AsyncMock(side_effect=DuplicateIdempotencyKeyError("Duplicate idempotency key: key-1"))
    outbox = mocker.MagicMock()
    outbox.save = mocker.AsyncMock()

    service = PaymentService(uow=FakeUow(payments=payments, outbox=outbox), event_routing_key="payments.new")

    result = await service.create_payment(make_command())

    assert result is existing
    outbox.save.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_payment_raises_entity_not_found(mocker):
    """Missing payment raises EntityNotFoundError with a stable code."""
    payments = mocker.MagicMock()
    payments.get_by_id = mocker.AsyncMock(return_value=None)
    outbox = mocker.MagicMock()

    service = PaymentService(uow=FakeUow(payments=payments, outbox=outbox), event_routing_key="payments.new")

    with pytest.raises(EntityNotFoundError) as exc_info:
        await service.get_payment(payment_id=uuid4())

    assert exc_info.value.code == "PAYMENT_NOT_FOUND"


@pytest.mark.asyncio
async def test_get_payment_returns_payment(mocker):
    """Existing payment is returned by id."""
    payment = make_payment()
    payments = mocker.MagicMock()
    payments.get_by_id = mocker.AsyncMock(return_value=payment)
    outbox = mocker.MagicMock()

    service = PaymentService(uow=FakeUow(payments=payments, outbox=outbox), event_routing_key="payments.new")

    result = await service.get_payment(payment_id=payment.id)  # type: ignore[arg-type]

    assert result is payment
