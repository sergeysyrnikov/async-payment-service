from abc import ABC, abstractmethod
from typing import Generic, TypeVar
from uuid import UUID

T = TypeVar("T")


class IRepository(ABC, Generic[T]):
    """Generic repository interface.

    Type parameter T represents the domain entity type managed by this repository.

    Example:
        class UserRepository(IRepository[User]):
            async def save(self, item: User) -> UUID: ...
            async def get_by_id(self, _id: UUID) -> User | None: ...
    """

    @abstractmethod
    async def save(
        self,
        item: T,
    ) -> UUID:
        """Persist a domain entity and return its UUID."""
        ...

    @abstractmethod
    async def get_by_id(
        self,
        _id: UUID,
    ) -> T | None:
        """Retrieve a domain entity by its UUID. Returns None if not found."""
        ...
