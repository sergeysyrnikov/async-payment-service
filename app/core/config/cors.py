"""CORS-specific settings."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class CORSSettings(BaseSettings):
    """CORS settings repository."""

    allow_origins: list[str] = Field(
        default_factory=lambda: ["*"],
        description="Список разрешённых источников (origins)",
    )
    allow_credentials: bool = Field(
        True,
        description="Разрешение использования учётных данных (credentials)",
    )
    allow_methods: list[str] = Field(
        default_factory=lambda: ["*"],
        description="Список разрешённых HTTP-методов",
    )
    allow_headers: list[str] = Field(
        default_factory=lambda: ["*"],
        description="Список разрешённых HTTP-заголовков",
    )

    model_config = SettingsConfigDict(
        env_prefix="CORS_",
    )
