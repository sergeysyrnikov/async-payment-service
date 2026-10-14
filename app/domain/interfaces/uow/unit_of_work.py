"""Unit of Work interface."""

from abc import ABC, abstractmethod
from typing import Self

from app.domain.interfaces.repository.outbox_repository import IOutboxRepository
from app.domain.interfaces.repository.payment_repository import IPaymentRepository


class IUnitOfWork(ABC):
    """Interface for Unit of Work."""

    @abstractmethod
    async def __aenter__(self) -> Self:
        """Enter the async context manager."""
        pass

    @abstractmethod
    async def __aexit__(self, exc_type: object, exc: BaseException | None, tb: object) -> None:
        """Exit the async context manager."""
        pass

    @property
    @abstractmethod
    def payments(self) -> IPaymentRepository:
        """Payments repository within the current unit of work."""
        pass

    @property
    @abstractmethod
    def outbox(self) -> IOutboxRepository:
        """Outbox repository within the current unit of work."""
        pass
