"""Payment ORM model."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import DateTime, Enum, Index, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.models.payment import Currency as DomainCurrency
from app.domain.models.payment import Payment as DomainPayment
from app.domain.models.payment import PaymentStatus as DomainPaymentStatus
from app.infrastructure.persistence.database import Base
from app.infrastructure.persistence.models.mixins import PrimaryKeyMixin, TimestampsMixin


class Payment(PrimaryKeyMixin, TimestampsMixin, Base):
    """ORM model for the ``payments`` table.

    Mapping is written manually (not via ``DomainMappingMixin``) because the
    domain field ``metadata`` cannot be used as an ORM attribute: ``metadata``
    is reserved by SQLAlchemy Declarative, so the column attribute is ``meta``.
    """

    __tablename__ = "payments"

    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[DomainCurrency] = mapped_column(
        Enum(
            DomainCurrency,
            name="payment_currency",
            values_callable=lambda cls: [m.value for m in cls],
        ),
        nullable=False,
    )
    description: Mapped[str] = mapped_column(Text, nullable=True)
    # «metadata» зарезервировано SQLAlchemy Declarative — атрибут называется meta
    meta: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    status: Mapped[DomainPaymentStatus] = mapped_column(
        Enum(
            DomainPaymentStatus,
            name="payment_status",
            values_callable=lambda cls: [m.value for m in cls],
        ),
        nullable=False,
        default=DomainPaymentStatus.PENDING,
    )
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    webhook_url: Mapped[str] = mapped_column(Text, nullable=False)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (Index("ix_payments_status", "status"),)

    def to_domain(self) -> DomainPayment:
        """Convert ORM model to domain entity."""
        return DomainPayment(
            id=self.id,
            amount=self.amount,
            currency=DomainCurrency(self.currency),
            description=self.description,
            metadata=dict(self.meta) if self.meta else {},
            status=DomainPaymentStatus(self.status),
            idempotency_key=self.idempotency_key,
            webhook_url=self.webhook_url,
            failure_reason=self.failure_reason,
            created_at=self.created_at,
            processed_at=self.processed_at,
        )

    @classmethod
    def from_domain(cls, domain: DomainPayment) -> Payment:
        """Convert domain entity to ORM model; DB defaults apply for None id/created_at."""
        kwargs: dict[str, Any] = {}
        if domain.id is not None:
            kwargs["id"] = domain.id
        if domain.created_at is not None:
            kwargs["created_at"] = domain.created_at
        return cls(
            amount=domain.amount,
            currency=domain.currency,
            description=domain.description,
            meta=dict(domain.metadata) if domain.metadata else {},
            status=domain.status,
            idempotency_key=domain.idempotency_key,
            webhook_url=domain.webhook_url,
            failure_reason=domain.failure_reason,
            processed_at=domain.processed_at,
            **kwargs,
        )
