"""Payment processing application service (consumer side use-case)."""

from decimal import Decimal

from aiologger import Logger  # type: ignore[import-untyped]

from app.application.commands.payment_commands import ProcessPaymentCommand
from app.domain.exceptions import ExternalServiceError
from app.domain.interfaces.services.payment_gateway import IPaymentGateway
from app.domain.interfaces.services.webhook_sender import IWebhookSender
from app.domain.interfaces.uow.unit_of_work import IUnitOfWork
from app.domain.models.payment import Payment, PaymentStatus


class PaymentProcessor:
    """Use-case: process a pending payment and notify the client via webhook."""

    def __init__(
        self,
        *,
        uow: IUnitOfWork,
        gateway: IPaymentGateway,
        webhook_sender: IWebhookSender,
        logger: Logger,
    ) -> None:
        self._uow = uow
        self._gateway = gateway
        self._webhook_sender = webhook_sender
        self._logger = logger

    async def process_payment(self, command: ProcessPaymentCommand) -> None:
        """Process a payment under a row lock and send the result webhook.

        The payment row is locked with SELECT ... FOR UPDATE for the whole
        processing, so concurrent consumers cannot process it twice. A
        non-positive amount (going below zero) is treated as a processing
        failure instead of raising an exception.
        """
        payment: Payment | None = None

        async with self._uow:
            payment = await self._uow.payments.get_for_update(payment_id=command.payment_id)
            if payment is None:
                await self._logger.warning(
                    "Payment not found, skipping message",
                    extra={"component": "payment_processor", "payment_id": str(command.payment_id)},
                )
                return

            if payment.status is not PaymentStatus.PENDING:
                await self._logger.info(
                    "Payment already processed, skipping message",
                    extra={
                        "component": "payment_processor",
                        "payment_id": str(command.payment_id),
                        "status": payment.status.value,
                    },
                )
                return

            status, reason = await self._resolve_status(payment)

            payment = await self._uow.payments.update_status(
                payment_id=command.payment_id,
                status=status,
                failure_reason=reason,
                processed_at=None,
            )

        if payment is None:
            return

        await self._send_webhook(payment)

    async def _resolve_status(self, payment: Payment) -> tuple[PaymentStatus, str | None]:
        """Emulate the gateway charge; a non-positive amount fails gracefully."""
        if payment.amount <= Decimal("0"):
            await self._logger.warning(
                "Payment amount is not positive, marking payment as failed",
                extra={"component": "payment_processor", "amount": str(payment.amount)},
            )
            return PaymentStatus.FAILED, "Payment amount must be positive"

        result = await self._gateway.process(amount=payment.amount, currency=payment.currency)
        if result.success:
            return PaymentStatus.SUCCEEDED, None
        return PaymentStatus.FAILED, result.reason or "Payment gateway declined the payment"

    async def _send_webhook(self, payment: Payment) -> None:
        """Deliver the result webhook; delivery failure is logged, not raised."""
        payload: dict = {
            "event": "payment.processed",
            "payment_id": str(payment.id),
            "status": payment.status.value if payment.status else None,
            "amount": str(payment.amount),
            "currency": payment.currency.value,
            "failure_reason": payment.failure_reason,
            "processed_at": payment.processed_at.isoformat() if payment.processed_at else None,
        }
        try:
            await self._webhook_sender.send(url=payment.webhook_url, payload=payload)
        except ExternalServiceError as exc:
            await self._logger.error(
                "Webhook delivery failed after retries",
                extra={
                    "component": "payment_processor",
                    "payment_id": str(payment.id),
                    "webhook_url": payment.webhook_url,
                },
                exc_info=exc,
            )
        else:
            await self._logger.info(
                "Webhook delivered",
                extra={"component": "payment_processor", "payment_id": str(payment.id)},
            )
