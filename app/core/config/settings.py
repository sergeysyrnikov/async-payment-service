"""Main settings repository."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.config.app import APPSettings
from app.core.config.cors import CORSSettings
from app.core.config.database import DatabaseSettings
from app.core.config.processing import PaymentProcessingSettings
from app.core.config.rabbit import RabbitSettings
from app.core.config.security import SecuritySettings
from app.core.config.sentry import SentrySettings


class Settings(BaseSettings):
    app: APPSettings = Field(
        default_factory=APPSettings,  # type: ignore[arg-type]
        description="Настройки приложения",
    )
    cors: CORSSettings = Field(
        default_factory=CORSSettings,  # type: ignore[arg-type]
        description="Настройки CORS",
    )
    db: DatabaseSettings = Field(
        default_factory=DatabaseSettings,  # type: ignore[arg-type]
        description="Настройки базы данных",
    )
    sentry: SentrySettings = Field(
        default_factory=SentrySettings,  # type: ignore[arg-type]
        description="Настройки Sentry",
    )
    rabbit: RabbitSettings = Field(
        default_factory=RabbitSettings,  # type: ignore[arg-type]
        description="Настройки RabbitMQ",
    )
    security: SecuritySettings = Field(
        default_factory=SecuritySettings,  # type: ignore[arg-type]
        description="Настройки безопасности",
    )
    processing: PaymentProcessingSettings = Field(
        default_factory=PaymentProcessingSettings,  # type: ignore[arg-type]
        description="Настройки процессинга платежей",
    )

    model_config = SettingsConfigDict()


settings = Settings()
