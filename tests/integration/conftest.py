from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.app import app


@pytest.fixture
def client(mock_async_logger):
    # Мокаем outbox relay: lifespan не должен ходить в RabbitMQ в тестах
    mock_relay = AsyncMock()
    app.container.outbox_relay.override(mock_relay)

    app.container.logger.override(mock_async_logger)

    with TestClient(app) as test_client:
        yield test_client

    app.container.outbox_relay.reset_override()
    app.container.logger.reset_override()


@pytest.fixture
def api_key() -> str:
    """Static API key used by the test application instance."""
    return app.container.security_settings().api_key


@pytest.fixture
def auth_headers(api_key) -> dict[str, str]:
    return {"X-API-Key": api_key}


@pytest.fixture
def container():
    return app.container
