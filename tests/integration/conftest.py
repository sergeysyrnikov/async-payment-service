
import pytest
from fastapi.testclient import TestClient

from app.app import app


@pytest.fixture
def client(mock_async_logger):
    app.container.logger.override(mock_async_logger)

    with TestClient(app) as test_client:
        yield test_client

    app.container.logger.reset_override()


@pytest.fixture
def container():
    return app.container
