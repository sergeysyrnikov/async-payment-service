"""Outbox ORM model."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.models.outbox_message import OutboxMessage as DomainOutboxMessage
from app.infrastructure.persistence.database import Base
from app.infrastructure.persistence.models.mixins import DomainMappingMixin, PrimaryKeyMixin


class OutboxMessage(PrimaryKeyMixin, DomainMappingMixin[DomainOutboxMessage], Base):
    """ORM model for the ``outbox`` table (transactional outbox pattern)."""

    __tablename__ = "outbox"
    __domain_cls__ = DomainOutboxMessage

    topic: Mapped[str] = mapped_column(String(255), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (Index("ix_outbox_published_at", "published_at"),)
