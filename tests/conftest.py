"""General test configuration and shared fixtures.

This conftest.py provides minimal general fixtures.
Consumer-specific tests use tests/consumer/conftest.py
for their specialized needs.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture(autouse=True)
def mock_settings(mocker) -> MagicMock:
    # Create comprehensive mock settings
    mock_settings = MagicMock()

    mocker.patch("app.core.config.settings.settings", mock_settings)

    return mock_settings


@pytest.fixture(autouse=True)
def mock_async_logger(mocker):
    """Mock the async logger to prevent pipe transport issues in tests."""
    # Create a simple mock logger that doesn"t use async streams
    mock_logger = AsyncMock()
    mock_logger.info = AsyncMock()
    mock_logger.error = AsyncMock()
    mock_logger.debug = AsyncMock()
    mock_logger.warning = AsyncMock()

    # Mock the setup_async_logging function
    mocker.patch("app.core.logging.setup_async_logging", return_value=mock_logger)

    return mock_logger
