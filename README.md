# Async Payment Service

Асинхронный сервис процессинга платежей: принимает платёжные запросы, обрабатывает их через
эмуляцию внешнего платёжного шлюза и уведомляет клиента о результате через webhook.

## Архитектура

```
 Клиент                API (FastAPI)                RabbitMQ              Consumer
  │  POST /payments ──►│                            │                    │
  │                    │ 1. payment + outbox row     │                    │
  │                    │    (одна транзакция БД)     │                    │
  │                    │ 2. Outbox relay ───────────►│ payments.new ─────►│ 3. эмуляция шлюза
  │                    │                            │                    │    (2–5 сек, 90% успех)
  │  GET /payments/id ◄│                            │                    │ 4. SELECT FOR UPDATE
  │                    │                            │  (ретраи/DLQ)      │    + update статуса
  │  ◄── webhook ─────────────────────────────────────────────────────────┘ 5. webhook (3 попытки)
```

Слои (Clean Architecture):

- `app/domain/` — модели (`Payment`, `OutboxMessage`), порты-интерфейсы, доменные исключения.
- `app/application/` — use-case сервисы (`PaymentService`, `PaymentProcessor`) и `Command` DTO.
- `app/infrastructure/` — SQLAlchemy-модели и репозитории, RabbitMQ (FastStream), эмуляция шлюза, webhook-отправка, outbox relay.
- `app/interfaces/` — FastAPI роутеры и Pydantic-схемы, статический API-ключ.
- `app/core/` — DI-контейнер, настройки, логирование, exception handlers.

## Гарантии доставки

- **Outbox pattern**: платёж и событие записываются в БД одной транзакцией; relay публикует
  события в RabbitMQ и помечает их опубликованными (at-least-once).
- **Устойчивость к недоступному брокеру**: API стартует даже если RabbitMQ недоступен —
  события накапливаются в outbox-таблице, relay ретраит подключение в фоне и публикует
  их, когда брокер вернётся.
- **Идемпотентность**: уникальный констрейнт на `idempotency_key`; повторный запрос с тем же
  `Idempotency-Key` возвращает уже созданный платёж; consumer пропускает уже обработанные платежи.
- **Ретраи**: обработка события — до `RABBITMQ_MAX_ATTEMPTS` (3) попыток с экспоненциальной
  задержкой (`x-retry-count` в заголовках сообщения); webhook — до 3 попыток с backoff.
- **DLQ**: сообщения, не обработанные после 3 попыток, попадают в очередь `payments.dead`
  через dead-letter exchange `payments.dlx`.
- **Блокировка строки**: при списании платёж берётся `SELECT ... FOR UPDATE`, поэтому
  конкурентные consumer-ы не обработают его дважды; отрицательная сумма помечает платёж
  как `failed`, а не роняет обработку.

## API

Все эндпойнты требуют заголовок `X-API-Key`.

`POST /payments` дополнительно требует заголовок `Idempotency-Key` (обязательный,
непустая строка): он обеспечивает идемпотентность — повторный вызов с тем же ключом
возвращает уже созданный платёж.

### Создание платежа

```bash
curl -X POST http://localhost:8001/api/v1/payments \
  -H "Content-Type: application/json" \
  -H "X-API-Key: change-me-in-production" \
  -H "Idempotency-Key: order-42-payment-1" \
  -d '{
    "amount": "100.50",
    "currency": "RUB",
    "description": "Заказ №42",
    "metadata": {"order_id": "42"},
    "webhook_url": "http://host.docker.internal:9000/webhook"
  }'
```

Ответ `202 Accepted`:

```json
{"payment_id": "…", "status": "pending", "created_at": "2026-10-13T10:00:00Z"}
```

### Получение платежа

```bash
curl http://localhost:8001/api/v1/payments/<payment_id> \
  -H "X-API-Key: change-me-in-production"
```

Ответ `200 OK` — полная детализация (`amount`, `currency`, `status`, `failure_reason`, `metadata`, …).
`404` с кодом `PAYMENT_NOT_FOUND` — платёж не найден.

### Webhook

После обработки (2–5 сек, ~90% успеха) на `webhook_url` приходит POST:

```json
{
  "event": "payment.processed",
  "payment_id": "…",
  "status": "succeeded",
  "amount": "100.50",
  "currency": "RUB",
  "failure_reason": null,
  "processed_at": "2026-10-13T10:00:05Z"
}
```

## Запуск

```bash
# 1. Скопировать .env.example -> .env и заполнить значения
cp .env.example .env

# 2. Создать внешнюю docker-сеть (один раз)
docker network create async_payment_service_network

# 3. Запустить стек: postgres, rabbitmq, migrations, api, consumer
docker compose up -d --build

# 4. Проверить
curl http://localhost:8001/api/v1/health/ -H "X-API-Key: $SECURITY_API_KEY"
```

Управление RabbitMQ: UI — http://localhost:15672 (guest/guest).

### Запуск миграций

Миграции применяются сервисом `async_payment_service_migrations` при `docker compose up`.
Вручную: `make migrations-up` (в Docker) или локально:

```bash
DATABASE_DSN='postgresql+asyncpg://USER:PASS@127.0.0.1:5444/DBNAME' uv run alembic upgrade head
```

### Запуск локально (вне Docker)

```bash
uv sync
uv run uvicorn app.app:app --port 8000        # API + outbox relay
uv run python -m app.consumer                 # consumer
```

## Переменные окружения

| Переменная | Описание | По умолчанию |
|---|---|---|
| `SECURITY_API_KEY` | Статический API-ключ (`X-API-Key`) | `change-me-in-production` |
| `RABBITMQ_URL` | URL подключения к RabbitMQ | `amqp://guest:guest@localhost:5672/` |
| `RABBITMQ_PAYMENT_QUEUE` | Очередь новых платежей | `payments.new` |
| `RABBITMQ_DEAD_LETTER_QUEUE` | DLQ для необработанных сообщений | `payments.dead` |
| `RABBITMQ_MAX_ATTEMPTS` | Попыток обработки сообщения | `3` |
| `RABBITMQ_RETRY_BASE_DELAY_SEC` | Базовая задержка ретрая (×2 за попытку) | `1.0` |
| `PAYMENT_PROCESSING_MIN_DELAY_SEC` / `MAX` | Диапазон задержки эмуляции шлюза | `2.0` / `5.0` |
| `PAYMENT_PROCESSING_SUCCESS_PROBABILITY` | Вероятность успешного списания | `0.9` |
| `PAYMENT_PROCESSING_WEBHOOK_MAX_ATTEMPTS` | Попыток доставки webhook | `3` |

Полный список — в `.env.example`.

## Тесты и проверки

```bash
uv run pytest               # тесты (unit + integration)
uv run mypy .               # типизация
uv run black . && uv run isort . && uv run ruff check .   # форматирование
```

Примечание: POST `/payments` возвращает `202 Accepted` (асинхронная обработка),
а не стандартный `201 Created` — это требование контракта.

