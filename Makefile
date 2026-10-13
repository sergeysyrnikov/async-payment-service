.PHONY: help up down restart logs ps build rebuild clean clean-pycache test lint format deps-update shell

# Default target
.DEFAULT_GOAL := help

# Docker compose files
COMPOSE_FILE = docker-compose.yml
DC := docker-compose -f $(COMPOSE_FILE)
SERVICE_NAME := bf_service
ALEMBIC := $(DC) exec -e PYTHONPATH=/app $(SERVICE_NAME) uv run alembic
APP_EXEC := $(DC) exec $(SERVICE_NAME)


# Execution context - can be overridden for CI
ifdef CI
    RUN_CMD := uv run
else
    RUN_CMD := $(APP_EXEC) uv run
endif

# Colors for help message
BLUE := \033[36m
NC := \033[0m

help: ## Show this help message
	@echo 'Usage:'
	@echo '  ${BLUE}make${NC} ${BLUE}<target>${NC}'
	@echo ''
	@echo 'Targets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  ${BLUE}%-15s${NC} %s\n", $$1, $$2}' $(MAKEFILE_LIST)

up: ## Start all services
	$(DC) up -d

down: ## Stop all services
	$(DC) down

restart: down up ## Restart all services

logs: ## Show logs from all services
	$(DC) logs -f

ps: ## List running services
	$(DC) ps

build: ## Build all services
	$(DC) build

rebuild: ## Rebuild all services from scratch
	$(DC) build --no-cache

clean: clean-pycache down ## Stop and remove containers, networks, and volumes
	$(DC) down -v --remove-orphans

clean-pycache: ## Remove __pycache__ (via container if up, else on host)
	@if docker compose -f $(COMPOSE_FILE) ps -q $(SERVICE_NAME) 2>/dev/null | grep -q .; then \
		$(APP_EXEC) find /app -type d -name __pycache__ -not -path '*/.venv/*' -exec rm -rf {} + 2>/dev/null || true; \
	else \
		find . -type d -name __pycache__ -not -path '*/.venv/*' -not -path '*/.git/*' -print0 | xargs -0 rm -rf 2>/dev/null || true; \
		find . -type f -name "*.pyc" -not -path '*/.venv/*' -not -path '*/.git/*' -delete 2>/dev/null || true; \
	fi

test: ## Run tests
	mkdir -p test-reports
	$(RUN_CMD) pytest tests/ --cov=. --cov-report=xml --cov-report=html --cov-report=term --junit-xml=test-reports/junit.xml

format: clean-pycache ## Format code
	$(RUN_CMD) black .
	$(RUN_CMD) ruff check --fix .
	$(RUN_CMD) isort .

lint: ## Run linters
	$(RUN_CMD) flake8
	$(RUN_CMD) black --check .
	$(RUN_CMD) isort --check-only .

type-check: ## Type checking
	$(RUN_CMD) mypy .

validate: clean-pycache format lint type-check ## Validate code (format + lint + type-check)

migrations-init: ## Initialize alembic migrations
	$(ALEMBIC) init migrations

migrations-create: ## Create new database migration
	$(ALEMBIC) revision --autogenerate -m ${MSG}

migrations-up: ## Apply all database migrations
	$(ALEMBIC) upgrade head

migrations-down: ## Rollback last database migration
	$(ALEMBIC) downgrade -1

deps-update: ## Update dependencies
	$(APP_EXEC) uv sync -U

shell: ## Open shell in app container
	$(APP_EXEC) /bin/bash
