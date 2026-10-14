"""Security settings."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class SecuritySettings(BaseSettings):
    """Settings for static API key authentication."""

    model_config = SettingsConfigDict(env_prefix="SECURITY_", case_sensitive=False)

    api_key: str = Field(
        "change-me-in-production",
        description="Статический API-ключ для доступа к эндпойнтам сервиса",
    )
