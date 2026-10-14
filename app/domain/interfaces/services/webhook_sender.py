"""Interface for webhook sender."""

from abc import ABC, abstractmethod
from typing import Any


class IWebhookSender(ABC):
    """Port for delivering webhook notifications to client URLs."""

    @abstractmethod
    async def send(
        self,
        *,
        url: str,
        payload: dict[str, Any],
    ) -> None:
        """Deliver a webhook payload to the given URL with retries."""
        ...
