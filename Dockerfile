# Базовый образ с uv
FROM ghcr.io/astral-sh/uv:python3.14-bookworm

# Указываем рабочую директорию
WORKDIR /app

# ENVS
ENV PYTHONPATH=/app \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

# Копируем проект
COPY . /app

# Ставим зависимости (uv сам создаст .venv)
RUN uv sync --frozen --no-dev

# Экспонируем порт
EXPOSE 8000

# Command to run the application in development mode
CMD ["uv", "run", "uvicorn", "app.app:app", "--host", "0.0.0.0", "--port", "8000"]
