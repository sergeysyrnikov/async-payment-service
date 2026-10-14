"""Payment gateway emulator: async processing with configurable success rate."""

from __future__ import annotations

import asyncio
import random
from decimal import Decimal

from aiologger import Logger  # type: ignore[import-untyped]

from app.core.config.processing import PaymentProcessingSettings
from app.domain.interfaces.services.payment_gateway import IPaymentGateway
from app.domain.models.payment import Currency, GatewayResult


class PaymentGatewayEmulator(IPaymentGateway):
    """Emulates an external payment gateway: random delay and success rate."""

    def __init__(
        self,
        *,
        settings: PaymentProcessingSettings,
        logger: Logger,
    ) -> None:
        self._settings = settings
        self._logger = logger

    async def process(
        self,
        *,
        amount: Decimal,
        currency: Currency,
    ) -> GatewayResult:
        """Emulate a gateway charge: sleep, then succeed with the configured probability."""
        delay = random.uniform(self._settings.min_delay_sec, self._settings.max_delay_sec)
        await asyncio.sleep(delay)

        if random.random() < self._settings.success_probability:
            await self._logger.info(
                "Payment gateway charge succeeded",
                extra={
                    "component": "payment_gateway",
                    "amount": str(amount),
                    "currency": currency.value,
                },
            )
            return GatewayResult(success=True)

        await self._logger.warning(
            "Payment gateway charge declined",
            extra={
                "component": "payment_gateway",
                "amount": str(amount),
                "currency": currency.value,
            },
        )
        return GatewayResult(
            success=False,
            reason="Payment gateway declined the payment",
        )
