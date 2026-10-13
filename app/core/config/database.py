"""Database repository settings."""

from pydantic import Field, PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    """Database repository settings."""

    dsn: PostgresDsn = Field(
        PostgresDsn(
            "postgresql+asyncpg://bf_service_db_user:bf_service_db_password@bf_service_postgres:5432/bf_service_db"
        ),
        description="URL для подключения к базе данных",
    )
    echo: bool = Field(
        False,
        description="Включение логирования SQL-запросов",
    )
    pool_size: int = Field(
        5,
        gt=0,
        description="Размер пула соединений",
    )
    max_overflow: int = Field(
        10,
        gt=0,
        description="Максимальное количество соединений сверх pool_size",
    )
    pool_timeout: int = Field(
        60,
        gt=0,
        description="Время ожидания соединения из пула в секундах",
    )
    pool_recycle: int = Field(
        3600,
        gt=0,
        description="Время жизни соединения в секундах до переподключения",
    )

    model_config = SettingsConfigDict(
        env_prefix="DATABASE_",
    )
