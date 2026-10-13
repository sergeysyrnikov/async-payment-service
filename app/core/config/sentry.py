"""Sentry configuration settings."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class SentrySettings(BaseSettings):
    """Sentry configuration."""

    dsn: str | None = Field(
        None,
        description="Sentry DSN для отслеживания ошибок. Если не задан, Sentry будет отключен.",
    )
    environment: str = Field(
        "development",
        description="Имя окружения для Sentry (например, production, staging, development)",
    )
    traces_sample_rate: float = Field(
        0.1,
        ge=0.0,
        le=1.0,
        description="Частота выборки для мониторинга производительности (от 0.0 до 1.0)",
    )
    profiles_sample_rate: float = Field(
        0.0,
        ge=0.0,
        le=1.0,
        description="Частота выборки для профилирования (от 0.0 до 1.0)",
    )

    model_config = SettingsConfigDict(
        env_prefix="SENTRY_",
        case_sensitive=False,
    )
