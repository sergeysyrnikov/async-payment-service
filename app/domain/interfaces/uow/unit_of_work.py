"""Unit of Work interface."""

from abc import ABC, abstractmethod
from typing import Self


class IUnitOfWork(ABC):
    """Interface for Unit of Work."""

    @abstractmethod
    async def __aenter__(self) -> Self:
        """Enter the async context manager."""
        pass

    @abstractmethod
    async def __aexit__(self, exc_type: object, exc: BaseException | None, tb: object) -> None:
        """Exit the async context manager."""
        pass
