"""SQLAlchemy implementation of :class:`app.domain.interfaces.uow.unit_of_work.IUnitOfWork`."""

from __future__ import annotations

from typing import Self

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.interfaces.repository.outbox_repository import IOutboxRepository
from app.domain.interfaces.repository.payment_repository import IPaymentRepository
from app.domain.interfaces.uow.unit_of_work import IUnitOfWork
from app.infrastructure.persistence.database import DatabaseManager
from app.infrastructure.persistence.outbox_repository import OutboxRepository
from app.infrastructure.persistence.payment_repository import PaymentRepository


class SqlAlchemyUnitOfWork(IUnitOfWork):
    """Async context manager: one ``AsyncSession`` and lazy repositories.

    Repositories use ``flush()`` for visibility within the unit; a successful exit
    calls ``commit()`` once; on exception, ``rollback()`` before ``close()``.
    """

    def __init__(self, db: DatabaseManager) -> None:
        self._db = db
        self._session: AsyncSession | None = None
        self._payments: PaymentRepository | None = None
        self._outbox: OutboxRepository | None = None

    async def __aenter__(self) -> Self:
        self._session = self._db.session_factory()
        return self

    async def __aexit__(self, exc_type: object, exc: BaseException | None, tb: object) -> None:
        if self._session is None:
            return
        try:
            if exc_type is not None:
                await self._session.rollback()
            else:
                await self._session.commit()
        finally:
            await self._session.close()

    @property
    def payments(self) -> IPaymentRepository:
        """Payments repository bound to the current session."""
        if self._session is None:
            msg = "Unit of work is not active (use async with SqlAlchemyUnitOfWork)"
            raise RuntimeError(msg)
        if self._payments is None:
            self._payments = PaymentRepository(self._session)
        return self._payments

    @property
    def outbox(self) -> IOutboxRepository:
        """Outbox repository bound to the current session."""
        if self._session is None:
            msg = "Unit of work is not active (use async with SqlAlchemyUnitOfWork)"
            raise RuntimeError(msg)
        if self._outbox is None:
            self._outbox = OutboxRepository(self._session)
        return self._outbox
