"""Unit tests for HttpWebhookSender."""

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.core.config.processing import PaymentProcessingSettings
from app.domain.exceptions import ExternalServiceError
from app.infrastructure.messaging.webhook_sender import HttpWebhookSender


class FakeResponse:
    """Minimal httpx.Response double."""

    def __init__(self, status_code: int) -> None:
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                f"HTTP {self.status_code}",
                request=MagicMock(),
                response=MagicMock(),
            )


@pytest.fixture
def settings() -> PaymentProcessingSettings:
    return PaymentProcessingSettings(
        webhook_timeout_sec=1.0,
        webhook_max_attempts=3,
        webhook_retry_base_delay_sec=1.0,
    )


@pytest.fixture
def mock_logger():
    logger = AsyncMock()
    logger.warning = AsyncMock()
    logger.error = AsyncMock()
    return logger


@pytest.fixture
def patch_client(mocker):
    """Patch httpx.AsyncClient used inside the sender."""

    def _patch(post_side_effects):
        client = AsyncMock()
        client.post = AsyncMock(side_effect=list(post_side_effects))
        ctx = MagicMock()
        ctx.__aenter__ = AsyncMock(return_value=client)
        ctx.__aexit__ = AsyncMock(return_value=None)
        return mocker.patch(
            "app.infrastructure.messaging.webhook_sender.httpx.AsyncClient",
            return_value=ctx,
        )

    return _patch


@pytest.mark.asyncio
async def test_send_success_first_attempt(settings, mock_logger, patch_client, mocker):
    """2xx response on the first attempt: no retries, no exception."""
    patch_client([FakeResponse(200)])
    sleep = mocker.patch("app.infrastructure.messaging.webhook_sender.asyncio.sleep", AsyncMock())

    sender = HttpWebhookSender(settings=settings, logger=mock_logger)
    await sender.send(url="https://example.com/hook", payload={"event": "payment.processed"})

    sleep.assert_not_awaited()


@pytest.mark.asyncio
async def test_send_retries_and_recovers(settings, mock_logger, patch_client, mocker):
    """First attempt fails with a transport error, second succeeds: one retry."""
    patch_client([httpx.ConnectError("boom"), FakeResponse(200)])
    sleep = mocker.patch("app.infrastructure.messaging.webhook_sender.asyncio.sleep", AsyncMock())

    sender = HttpWebhookSender(settings=settings, logger=mock_logger)
    await sender.send(url="https://example.com/hook", payload={})

    sleep.assert_awaited_once_with(1.0)


@pytest.mark.asyncio
async def test_send_raises_after_all_attempts(settings, mock_logger, patch_client, mocker):
    """All attempts fail: ExternalServiceError with a stable code; backoff grows exponentially."""
    patch_client([httpx.ConnectError("boom")] * 3)
    sleep = mocker.patch("app.infrastructure.messaging.webhook_sender.asyncio.sleep", AsyncMock())

    sender = HttpWebhookSender(settings=settings, logger=mock_logger)

    with pytest.raises(ExternalServiceError) as exc_info:
        await sender.send(url="https://example.com/hook", payload={})

    assert exc_info.value.code == "WEBHOOK_DELIVERY_FAILED"
    # Пауза после 1-й и 2-й попытки: 1.0 * 2**0 и 1.0 * 2**1
    assert [c.args[0] for c in sleep.await_args_list] == [1.0, 2.0]


@pytest.mark.asyncio
async def test_send_treats_http_error_status_as_failure(settings, mock_logger, patch_client, mocker):
    """HTTP 500 from the receiver counts as a failed attempt and triggers a retry."""
    patch_client([FakeResponse(500), FakeResponse(200)])
    sleep = mocker.patch("app.infrastructure.messaging.webhook_sender.asyncio.sleep", AsyncMock())

    sender = HttpWebhookSender(settings=settings, logger=mock_logger)
    await sender.send(url="https://example.com/hook", payload={})

    sleep.assert_awaited_once_with(1.0)
