from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from app.core.config.settings import settings


def test_root_endpoint(client: TestClient, container):
    """Test the root endpoint."""
    mock_logger = AsyncMock()

    with container.logger.override(mock_logger):
        response = client.get("/api/v1/")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["version"] == settings.app.version
    assert "timestamp" in data
    assert f"Welcome to {settings.app.name}" in data["message"]

    mock_logger.info.assert_called_once_with("Root endpoint accessed")
