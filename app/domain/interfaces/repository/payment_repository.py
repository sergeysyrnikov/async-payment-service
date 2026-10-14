"""Payment repository interface."""

from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from app.domain.interfaces.repository.repository import IRepository
from app.domain.models.payment import Payment, PaymentStatus


class IPaymentRepository(IRepository[Payment], ABC):
    """Repository port for payments."""

    @abstractmethod
    async def save(
        self,
        item: Payment,
    ) -> UUID:
        """Persist a domain entity and return its UUID."""
        ...

    @abstractmethod
    async def get_by_id(
        self,
        _id: UUID,
    ) -> Payment | None:
        """Retrieve a domain entity by its UUID. Returns None if not found."""
        ...

    @abstractmethod
    async def get_by_idempotency_key(
        self,
        *,
        idempotency_key: str,
    ) -> Payment | None:
        """Retrieve a payment by its idempotency key. Returns None if not found."""
        ...

    @abstractmethod
    async def get_for_update(
        self,
        *,
        payment_id: UUID,
    ) -> Payment | None:
        """Retrieve a payment with a row lock (SELECT ... FOR UPDATE)."""
        ...

    @abstractmethod
    async def update_status(
        self,
        *,
        payment_id: UUID,
        status: PaymentStatus,
        failure_reason: str | None = None,
        processed_at: datetime | None = None,
    ) -> Payment | None:
        """Lock the payment row and update its processing status."""
        ...
