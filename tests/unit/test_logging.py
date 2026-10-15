"""Unit tests for the JSON log formatter."""

import json
import logging

from aiologger.levels import LogLevel
from aiologger.records import ExtendedLogRecord

from app.core.logging import AsyncJSONFormatter


def test_formats_exception_instance_as_message() -> None:
    """uvicorn logs errors like logger.error(exc): msg IS an exception instance."""
    formatter = AsyncJSONFormatter()
    record = logging.LogRecord(
        name="uvicorn.error",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg=OSError(10048, "error while attempting to bind on address"),
        args=(),
        exc_info=None,
    )

    rendered = json.loads(formatter.format(record))

    assert "error while attempting to bind" in rendered["message"]
    assert rendered["level"] == "ERROR"


def test_formats_aiologger_record() -> None:
    """aiologger's ExtendedLogRecord has no getMessage(): formatter falls back to str()."""
    formatter = AsyncJSONFormatter()
    record = ExtendedLogRecord(
        name="app",
        level=LogLevel.INFO,
        pathname=__file__,
        lineno=1,
        msg="Outbox relay started",
        args=None,
        exc_info=None,
        extra={},
        flatten=False,
        serializer_kwargs=None,
    )

    rendered = json.loads(formatter.format(record))

    assert rendered["message"] == "Outbox relay started"
    assert rendered["level"] == "INFO"


def test_formats_regular_record() -> None:
    """A regular printf-style record renders to valid JSON."""
    formatter = AsyncJSONFormatter()
    record = logging.LogRecord(
        name="app",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="Outbox relay started",
        args=(),
        exc_info=None,
    )

    rendered = json.loads(formatter.format(record))

    assert rendered["message"] == "Outbox relay started"
    assert rendered["level"] == "INFO"
