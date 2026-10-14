"""Unit tests for PaymentGatewayEmulator."""

from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from app.core.config.processing import PaymentProcessingSettings
from app.domain.models.payment import Currency
from app.infrastructure.messaging.payment_gateway_emulator import PaymentGatewayEmulator


@pytest.fixture
def settings() -> PaymentProcessingSettings:
    return PaymentProcessingSettings(
        min_delay_sec=2.0,
        max_delay_sec=5.0,
        success_probability=0.9,
    )


@pytest.fixture
def mock_logger():
    logger = AsyncMock()
    logger.info = AsyncMock()
    logger.warning = AsyncMock()
    return logger


@pytest.mark.asyncio
async def test_gateway_sleeps_within_bounds(settings, mock_logger, mocker):
    """The emulator sleeps for a random delay within [min, max]."""
    mocker.patch("app.infrastructure.messaging.payment_gateway_emulator.random.uniform", return_value=3.5)
    mocker.patch("app.infrastructure.messaging.payment_gateway_emulator.random.random", return_value=0.5)
    sleep = mocker.patch("app.infrastructure.messaging.payment_gateway_emulator.asyncio.sleep", AsyncMock())

    gateway = PaymentGatewayEmulator(settings=settings, logger=mock_logger)
    result = await gateway.process(amount=Decimal("100.00"), currency=Currency.RUB)

    sleep.assert_awaited_once_with(3.5)
    assert result.success is True


@pytest.mark.asyncio
async def test_gateway_success(settings, mock_logger, mocker):
    """A random roll below the success probability succeeds."""
    mocker.patch("app.infrastructure.messaging.payment_gateway_emulator.random.uniform", return_value=2.0)
    mocker.patch("app.infrastructure.messaging.payment_gateway_emulator.random.random", return_value=0.5)
    mocker.patch("app.infrastructure.messaging.payment_gateway_emulator.asyncio.sleep", AsyncMock())

    gateway = PaymentGatewayEmulator(settings=settings, logger=mock_logger)
    result = await gateway.process(amount=Decimal("100.00"), currency=Currency.USD)

    assert result.success is True
    assert result.reason is None


@pytest.mark.asyncio
async def test_gateway_decline(settings, mock_logger, mocker):
    """A random roll above the success probability declines with a reason."""
    mocker.patch("app.infrastructure.messaging.payment_gateway_emulator.random.uniform", return_value=2.0)
    mocker.patch("app.infrastructure.messaging.payment_gateway_emulator.random.random", return_value=0.95)
    mocker.patch("app.infrastructure.messaging.payment_gateway_emulator.asyncio.sleep", AsyncMock())

    gateway = PaymentGatewayEmulator(settings=settings, logger=mock_logger)
    result = await gateway.process(amount=Decimal("100.00"), currency=Currency.EUR)

    assert result.success is False
    assert result.reason == "Payment gateway declined the payment"
