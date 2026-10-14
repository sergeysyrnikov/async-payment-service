"""Webhook sender: HTTP delivery with retries and exponential backoff."""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
from aiologger import Logger  # type: ignore[import-untyped]

from app.core.config.processing import PaymentProcessingSettings
from app.domain.exceptions import ExternalServiceError
from app.domain.interfaces.services.webhook_sender import IWebhookSender


class HttpWebhookSender(IWebhookSender):
    """Delivers webhook notifications via HTTP POST with retries."""

    def __init__(
        self,
        *,
        settings: PaymentProcessingSettings,
        logger: Logger,
    ) -> None:
        self._settings = settings
        self._logger = logger

    async def send(
        self,
        *,
        url: str,
        payload: dict[str, Any],
    ) -> None:
        """POST the payload; retries with exponential backoff, then raises ExternalServiceError."""
        last_error: Exception | None = None

        async with httpx.AsyncClient(timeout=self._settings.webhook_timeout_sec) as client:
            for attempt in range(1, self._settings.webhook_max_attempts + 1):
                try:
                    response = await client.post(url, json=payload)
                    response.raise_for_status()
                    return
                except httpx.HTTPError as exc:
                    last_error = exc
                    await self._logger.warning(
                        "Webhook delivery attempt failed",
                        extra={
                            "component": "webhook_sender",
                            "url": url,
                            "attempt": attempt,
                        },
                        exc_info=exc,
                    )
                    if attempt < self._settings.webhook_max_attempts:
                        delay = self._settings.webhook_retry_base_delay_sec * (2 ** (attempt - 1))
                        await asyncio.sleep(delay)

        raise ExternalServiceError(
            "webhook",
            f"Webhook delivery failed after {self._settings.webhook_max_attempts} attempts: {last_error}",
            code="WEBHOOK_DELIVERY_FAILED",
        )
