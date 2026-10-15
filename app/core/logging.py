import asyncio
import json
import logging
import sys
import traceback
from datetime import datetime
from typing import Any, Dict

from aiologger import Logger  # type: ignore
from aiologger.formatters.base import Formatter  # type: ignore
from aiologger.handlers.base import Handler  # type: ignore
from aiologger.levels import LogLevel  # type: ignore
from aiologger.loggers.json import JsonLogger  # type: ignore
from aiologger.records import LogRecord  # type: ignore

from app.core.config.settings import settings


class AsyncJSONFormatter(Formatter):
    """Custom JSON formatter for structured logging."""

    def format_exception(
        self,
        exc_info: tuple,
    ) -> str:
        """Format exception info as a string."""
        return "".join(traceback.format_exception(*exc_info))

    def format(
        self,
        record: LogRecord,
    ) -> str:
        """Format log record as JSON string."""
        # getMessage() есть у std-записей (и строкует msg-исключения, как logger.error(exc)
        # у uvicorn); у aiologger ExtendedLogRecord его нет — падаем на str()
        get_message = getattr(record, "getMessage", None)
        if get_message is not None:
            record.message = get_message()
        else:
            record.message = str(record.msg % record.args) if record.args else str(record.msg)

        # Base log record attributes
        log_object: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "message": record.message,
            "module": record.module,
            "function": getattr(record, "funcName", None),
            "line": record.lineno,
        }

        # Add request_id if available
        if hasattr(record, "request_id"):
            log_object["request_id"] = record.request_id

        # Извлекаем extra от aiologger (добавляется JsonLogger-ом как вложенный словарь)
        if hasattr(record, "extra") and isinstance(record.extra, dict):
            log_object.update(record.extra)

        # Add exception info if available
        if record.exc_info:
            log_object["exception"] = self.format_exception(record.exc_info)

        return json.dumps(log_object, default=str)


class AsyncPrintHandler(Handler):
    """Cross-platform async stream handler.

    Unlike aiologger's AsyncStreamHandler, it does not use
    ``loop.connect_write_pipe()``, which is unsupported on Windows event loops,
    and writes to the stream via ``asyncio.to_thread`` instead.
    """

    terminator = "\n"

    def __init__(
        self,
        stream: Any = None,
        level: int | LogLevel = LogLevel.NOTSET,
        formatter: Formatter | None = None,
    ) -> None:
        super().__init__(level=level)
        if stream is None:
            stream = sys.stderr
        self.stream = stream
        if formatter is None:
            formatter = Formatter()
        self.formatter = formatter

    @property
    def initialized(self) -> bool:
        return True

    async def emit(self, record: LogRecord) -> None:
        """Format record and write it to the stream."""
        try:
            msg = self.formatter.format(record) + self.terminator
            await asyncio.to_thread(self.stream.write, msg)
        except Exception as exc:
            await self.handle_error(record, exc)

    async def flush(self) -> None:
        """Flush the underlying stream."""
        try:
            await asyncio.to_thread(self.stream.flush)
        except Exception:
            pass

    async def close(self) -> None:
        """Flush the stream; nothing else to release."""
        await self.flush()


def setup_async_logging() -> Logger:
    """Configure async application logging."""
    # Используем JsonLogger для того чтобы сохранялся параметр extra=...
    logger = JsonLogger(
        name="app_logger",
        level=LogLevel.DEBUG if settings.app.debug else LogLevel.INFO,
    )

    # Create async console handler (cross-platform, works on Windows too)
    console_handler = AsyncPrintHandler(
        stream=sys.stdout,
    )
    console_handler.formatter = AsyncJSONFormatter()
    logger.add_handler(console_handler)

    return logger


class AioHandler(logging.Handler):
    def __init__(
        self,
        aio_logger: Logger,
    ):
        super().__init__()
        self.aio_logger = aio_logger

    async def emit_async(
        self,
        logger: Logger,
        record: LogRecord,
    ) -> None:
        await logger.handle(record)

    def emit(
        self,
        record: LogRecord,
    ) -> None:
        if record.name == self.aio_logger.name:
            return

        try:
            asyncio.get_running_loop().call_soon_threadsafe(
                lambda: asyncio.create_task(self.emit_async(self.aio_logger, record))
            )
        except Exception:
            self.handleError(record)


def patch_uvicorn_loggers(
    aio_logger: Logger,
) -> None:
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(name)
        logger.handlers = []  # очищаем стандартные хендлеры
        logger.propagate = False  # важно
        logger.addHandler(AioHandler(aio_logger))
        logger.setLevel(logging.INFO)
