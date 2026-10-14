"""Outbox message repository interface."""

from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.interfaces.repository.repository import IRepository
from app.domain.models.outbox_message import OutboxMessage


class IOutboxRepository(IRepository[OutboxMessage], ABC):
    """Repository port for outbox messages."""

    @abstractmethod
    async def save(
        self,
        item: OutboxMessage,
    ) -> UUID:
        """Persist a domain entity and return its UUID."""
        ...

    @abstractmethod
    async def get_by_id(
        self,
        _id: UUID,
    ) -> OutboxMessage | None:
        """Retrieve a domain entity by its UUID. Returns None if not found."""
        ...

    @abstractmethod
    async def fetch_unpublished(
        self,
        *,
        limit: int,
    ) -> list[OutboxMessage]:
        """Fetch unpublished outbox messages with row locks (FOR UPDATE SKIP LOCKED)."""
        ...

    @abstractmethod
    async def mark_published(
        self,
        *,
        message_ids: list[UUID],
    ) -> int:
        """Mark outbox messages as published. Returns the number of updated rows."""
        ...
