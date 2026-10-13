from unittest.mock import AsyncMock

from fastapi.testclient import TestClient


def test_health_check_api(client: TestClient, container):
    """Test health check API endpoint."""
    # Create a mock health service
    mock_health_service = AsyncMock()
    mock_health_service.check.return_value = {"database": "up", "status": "up"}

    # Override the health_service dependency
    with container.health_service.override(mock_health_service):
        response = client.get("/api/v1/health/")

    assert response.status_code == 200
    assert response.json() == {"database": "up", "status": "up"}
    mock_health_service.check.assert_called_once()
