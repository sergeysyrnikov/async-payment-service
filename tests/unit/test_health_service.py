from contextlib import asynccontextmanager
from typing import AsyncIterator, cast
from unittest.mock import AsyncMock

import pytest

from app.application.services.health_service import HealthService
from app.infrastructure.persistence.database import DatabaseManager


class _FakeDatabaseManager:
    def __init__(self, session: AsyncMock) -> None:
        self._session = session

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncMock]:
        yield self._session


@pytest.mark.asyncio
async def test_health_check_returns_up_for_database() -> None:
    session = AsyncMock()
    db = cast(DatabaseManager, _FakeDatabaseManager(session=session))
    service = HealthService(db=db)

    result = await service.check()

    assert result == {
        "api": "up",
        "postgresql": "up",
    }


@pytest.mark.asyncio
async def test_health_check_returns_down_when_database_fails() -> None:
    session = AsyncMock()
    session.execute.side_effect = RuntimeError("db is unavailable")
    db = cast(DatabaseManager, _FakeDatabaseManager(session=session))
    service = HealthService(db=db)

    result = await service.check()

    assert result == {
        "api": "up",
        "postgresql": "down",
    }
