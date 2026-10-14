"""Interface for event publisher."""

from abc import ABC, abstractmethod
from typing import Any


class IEventPublisher(ABC):
    """Port for publishing integration events to a message broker."""

    @abstractmethod
    async def start(self) -> None:
        """Connect the underlying transport."""
        ...

    @abstractmethod
    async def stop(self) -> None:
        """Close the underlying transport."""
        ...

    @abstractmethod
    async def publish(
        self,
        *,
        routing_key: str,
        payload: dict[str, Any],
        headers: dict[str, Any] | None = None,
    ) -> None:
        """Publish an event payload to the given routing key."""
        ...
