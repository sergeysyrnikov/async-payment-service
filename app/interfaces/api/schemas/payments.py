"""Pydantic schemas for the payments API."""

from dataclasses import asdict
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl

from app.domain.models.payment import Currency, Payment, PaymentStatus


class PaymentInDto(BaseModel):
    """HTTP request body for payment creation."""

    amount: Decimal = Field(..., gt=Decimal("0"), max_digits=12, decimal_places=2, description="Сумма платежа")
    currency: Currency = Field(..., description="Валюта платежа: RUB, USD или EUR")
    description: str | None = Field(None, description="Описание платежа")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Дополнительные метаданные платежа")
    webhook_url: HttpUrl = Field(..., description="URL для webhook-уведомления о результате обработки")


class PaymentCreatedOutDto(BaseModel):
    """HTTP response body for a created payment (202 Accepted)."""

    payment_id: UUID = Field(..., description="Уникальный идентификатор платежа")
    status: PaymentStatus = Field(..., description="Статус обработки платежа")
    created_at: datetime = Field(..., description="Дата и время создания платежа")

    @classmethod
    def from_domain(cls, payment: Payment) -> "PaymentCreatedOutDto":
        """Build the DTO from a domain payment entity."""
        return cls(
            payment_id=payment.id,  # type: ignore[arg-type]
            status=payment.status,
            created_at=payment.created_at,  # type: ignore[arg-type]
        )


class PaymentOutDto(BaseModel):
    """HTTP response body with full payment details."""

    payment_id: UUID = Field(..., description="Уникальный идентификатор платежа")
    amount: Decimal = Field(..., description="Сумма платежа")
    currency: Currency = Field(..., description="Валюта платежа")
    description: str | None = Field(None, description="Описание платежа")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Метаданные платежа")
    status: PaymentStatus = Field(..., description="Статус обработки платежа")
    idempotency_key: str = Field(..., description="Ключ идемпотентности платежа")
    webhook_url: str = Field(..., description="URL для webhook-уведомлений")
    failure_reason: str | None = Field(None, description="Причина отказа при обработке")
    created_at: datetime = Field(..., description="Дата и время создания платежа")
    processed_at: datetime | None = Field(None, description="Дата и время завершения обработки")

    @classmethod
    def from_domain(cls, payment: Payment) -> "PaymentOutDto":
        """Build the DTO from a domain payment entity."""
        data = asdict(payment)
        return cls(
            payment_id=data["id"],
            amount=data["amount"],
            currency=data["currency"],
            description=data["description"],
            metadata=data["metadata"],
            status=data["status"],
            idempotency_key=data["idempotency_key"],
            webhook_url=data["webhook_url"],
            failure_reason=data["failure_reason"],
            created_at=data["created_at"],
            processed_at=data["processed_at"],
        )
