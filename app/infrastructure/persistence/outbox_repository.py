"""SQLAlchemy implementation of the outbox repository."""

from __future__ import annotations

from typing import Any, cast
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.engine.cursor import CursorResult

from app.domain.interfaces.repository.outbox_repository import IOutboxRepository
from app.domain.models.outbox_message import OutboxMessage as DomainOutboxMessage
from app.infrastructure.persistence.base_repository import BaseRepository
from app.infrastructure.persistence.models.outbox import OutboxMessage as OutboxModel


class OutboxRepository(BaseRepository, IOutboxRepository):
    """SQLAlchemy repository for outbox messages."""

    async def save(self, item: DomainOutboxMessage) -> UUID:
        """Persist an outbox message within the current unit of work."""
        model = OutboxModel.from_domain(item)
        self._session.add(model)
        # flush (не commit): получаем id внутри транзакции UoW — коммит делает UoW
        await self._session.flush()
        assert model.id is not None
        return model.id

    async def get_by_id(self, _id: UUID) -> DomainOutboxMessage | None:
        """Retrieve an outbox message by id; returns None if not found."""
        result = await self._session.execute(
            select(OutboxModel).where(OutboxModel.id == _id),
        )
        model = result.scalar_one_or_none()
        return model.to_domain() if model is not None else None

    async def fetch_unpublished(self, *, limit: int) -> list[DomainOutboxMessage]:
        """Fetch unpublished messages with FOR UPDATE SKIP LOCKED locks."""
        result = await self._session.execute(
            select(OutboxModel)
            .where(OutboxModel.published_at.is_(None))
            .order_by(OutboxModel.created_at)
            .limit(limit)
            .with_for_update(skip_locked=True),
        )
        models = result.scalars().all()
        return [model.to_domain() for model in models]

    async def mark_published(self, *, message_ids: list[UUID]) -> int:
        """Mark outbox messages as published; returns the number of updated rows."""
        if not message_ids:
            return 0
        statement = (
            update(OutboxModel)
            .where(OutboxModel.id.in_(message_ids), OutboxModel.published_at.is_(None))
            .values(published_at=func.now())
            .execution_options(synchronize_session=False)
        )
        result = cast(
            "CursorResult[Any]",
            await self._session.execute(statement),
        )
        # rowcount есть у CursorResult, но отсутствует в типе Result в стабах SQLAlchemy
        return result.rowcount or 0
