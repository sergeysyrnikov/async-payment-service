"""RabbitMQ settings."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class RabbitSettings(BaseSettings):
    """Settings for RabbitMQ connection and topology."""

    model_config = SettingsConfigDict(env_prefix="RABBITMQ_", case_sensitive=False)

    url: str = Field(
        "amqp://guest:guest@localhost:5672/",
        description="URL для подключения к RabbitMQ",
    )
    exchange: str = Field(
        "payments.events",
        description="Имя основного exchange для событий платежей",
    )
    payment_queue: str = Field(
        "payments.new",
        description="Имя очереди новых платежей",
    )
    payment_routing_key: str = Field(
        "payments.new",
        description="Routing key для событий новых платежей",
    )
    dead_letter_exchange: str = Field(
        "payments.dlx",
        description="Имя dead-letter exchange для сообщений после исчерпания попыток",
    )
    dead_letter_queue: str = Field(
        "payments.dead",
        description="Имя очереди недоставленных сообщений (DLQ)",
    )
    dead_letter_routing_key: str = Field(
        "payments.dead",
        description="Routing key для DLQ",
    )
    max_attempts: int = Field(
        3,
        ge=1,
        description="Максимальное количество попыток обработки сообщения",
    )
    retry_base_delay_sec: float = Field(
        1.0,
        gt=0,
        description="Базовая задержка повтора (растёт экспоненциально)",
    )
    outbox_poll_interval_sec: float = Field(
        1.0,
        gt=0,
        description="Интервал опроса outbox-таблицы в секундах",
    )
    outbox_batch_size: int = Field(
        50,
        ge=1,
        description="Размер выборки outbox-сообщений за одну итерацию",
    )
