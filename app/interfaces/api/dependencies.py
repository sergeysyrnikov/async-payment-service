"""Header dependencies for HTTP endpoints."""

from typing import Annotated

from dependency_injector.wiring import Provide, inject
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import APIKeyHeader

from app.core.config.security import SecuritySettings
from app.core.di.containers import Container

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


@inject
async def require_api_key(
    x_api_key: Annotated[str | None, Depends(api_key_header)],
    security_settings: Annotated[SecuritySettings, Depends(Provide[Container.security_settings])],
) -> str:
    """Validate the static X-API-Key header; 401 on a missing or wrong key."""
    if x_api_key is None or x_api_key != security_settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )
    return x_api_key


async def require_idempotency_key(
    idempotency_key: Annotated[
        str,
        Header(
            alias="Idempotency-Key",
            description="Ключ идемпотентности платежа (обязательный)",
        ),
    ],
) -> str:
    """Require the Idempotency-Key header (обязательный по ТЗ).

    Отсутствующий заголовок отклоняется валидацией FastAPI (422);
    пустое значение или одни пробелы — 400 здесь.
    """
    if not idempotency_key.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Idempotency-Key header must be a non-empty string",
        )
    return idempotency_key
