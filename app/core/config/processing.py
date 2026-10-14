"""Payment processing settings."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class PaymentProcessingSettings(BaseSettings):
    """Settings for payment gateway emulation and webhook delivery."""

    model_config = SettingsConfigDict(env_prefix="PAYMENT_PROCESSING_", case_sensitive=False)

    min_delay_sec: float = Field(
        2.0,
        gt=0,
        description="Минимальная задержка эмуляции обработки платежа в секундах",
    )
    max_delay_sec: float = Field(
        5.0,
        gt=0,
        description="Максимальная задержка эмуляции обработки платежа в секундах",
    )
    success_probability: float = Field(
        0.9,
        ge=0.0,
        le=1.0,
        description="Вероятность успешного списания при эмуляции шлюза",
    )
    webhook_timeout_sec: float = Field(
        10.0,
        gt=0,
        description="Таймаут HTTP-запроса webhook-уведомления в секундах",
    )
    webhook_max_attempts: int = Field(
        3,
        ge=1,
        description="Максимальное количество попыток отправки webhook-уведомления",
    )
    webhook_retry_base_delay_sec: float = Field(
        1.0,
        gt=0,
        description="Базовая задержка повтора webhook (растёт экспоненциально)",
    )
