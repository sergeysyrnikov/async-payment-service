"""Base SQLAlchemy repository helpers.

This module contains infrastructure-level abstractions for repositories that
use SQLAlchemy AsyncSession. Domain layer must not depend on SQLAlchemy.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession


class BaseRepository:
    """Base class for SQLAlchemy repositories."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @property
    def session(self) -> AsyncSession:
        """Return the current SQLAlchemy session."""

        return self._session
