"""Payment application service: use-cases for the payments API."""

from dataclasses import asdict
from uuid import UUID

from app.application.commands.payment_commands import CreatePaymentCommand
from app.domain.exceptions import DuplicateIdempotencyKeyError, EntityNotFoundError
from app.domain.interfaces.uow.unit_of_work import IUnitOfWork
from app.domain.models.outbox_message import OutboxMessage
from app.domain.models.payment import Payment


class PaymentService:
    """Use-cases for creating and reading payments (transactional outbox)."""

    def __init__(
        self,
        *,
        uow: IUnitOfWork,
        event_routing_key: str,
    ) -> None:
        self._uow = uow
        self._event_routing_key = event_routing_key

    async def create_payment(self, command: CreatePaymentCommand) -> Payment:
        """Create a payment; returns the existing one for a repeated idempotency key."""
        try:
            async with self._uow:
                existing = await self._uow.payments.get_by_idempotency_key(
                    idempotency_key=command.idempotency_key,
                )
                if existing is not None:
                    return existing

                payment = Payment(**asdict(command))
                saved_id = await self._uow.payments.save(payment)
                await self._uow.outbox.save(
                    OutboxMessage(
                        topic=self._event_routing_key,
                        payload={"event": "payment.created", "payment_id": str(saved_id)},
                    ),
                )
        except DuplicateIdempotencyKeyError:
            # Гонка двух запросов с одним ключом: UNIQUE-констрейнт отклонил дубль.
            existing = await self._get_by_idempotency_key(command.idempotency_key)
            if existing is not None:
                return existing
            raise

        reloaded = await self.get_payment(payment_id=saved_id)
        return reloaded

    async def get_payment(self, *, payment_id: UUID) -> Payment:
        """Return the payment by id; raises EntityNotFoundError if absent."""
        payment = await self._get_by_id(payment_id)
        if payment is None:
            raise EntityNotFoundError(
                message=f"Payment not found: id={payment_id}",
                code="PAYMENT_NOT_FOUND",
            )
        return payment

    async def _get_by_id(self, payment_id: UUID) -> Payment | None:
        async with self._uow:
            return await self._uow.payments.get_by_id(payment_id)

    async def _get_by_idempotency_key(self, idempotency_key: str) -> Payment | None:
        async with self._uow:
            return await self._uow.payments.get_by_idempotency_key(idempotency_key=idempotency_key)
