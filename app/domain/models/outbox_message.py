"""Outbox message domain model (transactional outbox pattern)."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID


@dataclass
class OutboxMessage:
    """A message persisted atomically with business data and published later."""

    topic: str
    payload: dict[str, Any]
    id: UUID | None = None
    created_at: datetime | None = None
    published_at: datetime | None = None
