"""SQLAlchemy implementation of the payments repository."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.domain.exceptions import DuplicateIdempotencyKeyError
from app.domain.interfaces.repository.payment_repository import IPaymentRepository
from app.domain.models.payment import Payment as DomainPayment
from app.domain.models.payment import PaymentStatus
from app.infrastructure.persistence.base_repository import BaseRepository
from app.infrastructure.persistence.models.payment import Payment as PaymentModel


class PaymentRepository(BaseRepository, IPaymentRepository):
    """SQLAlchemy repository for payments."""

    async def save(self, item: DomainPayment) -> UUID:
        """Persist a payment within the current unit of work."""
        model = PaymentModel.from_domain(item)
        self._session.add(model)
        try:
            # flush (не commit): получаем id и ловим нарушение UNIQUE(idempotency_key)
            # ещё внутри транзакции UoW — коммит делает UoW на выходе
            await self._session.flush()
        except IntegrityError as exc:
            await self._session.rollback()
            raise DuplicateIdempotencyKeyError(
                f"Duplicate idempotency key: {item.idempotency_key}",
            ) from exc
        assert model.id is not None
        return model.id

    async def get_by_id(self, _id: UUID) -> DomainPayment | None:
        """Retrieve a payment by id; returns None if not found."""
        result = await self._session.execute(
            select(PaymentModel).where(PaymentModel.id == _id),
        )
        model = result.scalar_one_or_none()
        return model.to_domain() if model is not None else None

    async def get_by_idempotency_key(self, *, idempotency_key: str) -> DomainPayment | None:
        """Retrieve a payment by its idempotency key; returns None if not found."""
        result = await self._session.execute(
            select(PaymentModel).where(PaymentModel.idempotency_key == idempotency_key),
        )
        model = result.scalar_one_or_none()
        return model.to_domain() if model is not None else None

    async def get_for_update(self, *, payment_id: UUID) -> DomainPayment | None:
        """Retrieve a payment with a row lock (SELECT ... FOR UPDATE)."""
        result = await self._session.execute(
            select(PaymentModel).where(PaymentModel.id == payment_id).with_for_update(),
        )
        model = result.scalar_one_or_none()
        return model.to_domain() if model is not None else None

    async def update_status(
        self,
        *,
        payment_id: UUID,
        status: PaymentStatus,
        failure_reason: str | None = None,
        processed_at: datetime | None = None,
    ) -> DomainPayment | None:
        """Lock the payment row (FOR UPDATE) and update its processing status."""
        result = await self._session.execute(
            select(PaymentModel).where(PaymentModel.id == payment_id).with_for_update(),
        )
        model = result.scalar_one_or_none()
        if model is None:
            return None

        model.status = status
        model.failure_reason = failure_reason
        if processed_at is not None:
            model.processed_at = processed_at
        await self._session.flush()
        return model.to_domain()
