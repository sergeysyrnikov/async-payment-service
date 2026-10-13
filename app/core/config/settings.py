"""Main settings repository."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.config.app import APPSettings
from app.core.config.cors import CORSSettings
from app.core.config.database import DatabaseSettings
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

    model_config = SettingsConfigDict()


settings = Settings()
