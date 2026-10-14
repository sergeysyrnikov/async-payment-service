"""Payment use-case commands."""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any
from uuid import UUID

from app.domain.models.payment import Currency


@dataclass
class CreatePaymentCommand:
    """Command for creating a new payment."""

    amount: Decimal
    currency: Currency
    idempotency_key: str
    webhook_url: str
    description: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ProcessPaymentCommand:
    """Command for processing a pending payment (consumer side)."""

    payment_id: UUID
