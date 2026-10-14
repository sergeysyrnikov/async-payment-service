"""Payment domain model."""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID


class PaymentStatus(StrEnum):
    """Allowed values for payment processing status."""

    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class Currency(StrEnum):
    """Allowed payment currencies."""

    RUB = "RUB"
    USD = "USD"
    EUR = "EUR"


@dataclass
class GatewayResult:
    """Result of an external payment gateway processing call."""

    success: bool
    reason: str | None = None


@dataclass
class Payment:
    """Payment aggregate: a single client payment processed asynchronously."""

    amount: Decimal
    currency: Currency
    idempotency_key: str
    webhook_url: str
    description: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    status: PaymentStatus = PaymentStatus.PENDING
    failure_reason: str | None = None
    id: UUID | None = None
    created_at: datetime | None = None
    processed_at: datetime | None = None
