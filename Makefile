.PHONY: dev install db db-down test lint fmt coverage help

help:
	@echo "cadence — LLM-based program evolution"
	@echo ""
	@echo "Quick start:"
	@echo "  make dev       - Clone-to-running: dependencies, database, schema"
	@echo "  make install   - Dependencies only"
	@echo "  make db        - Start Postgres and Redis, then migrate both databases"
	@echo "  make db-down   - Stop them, keeping the data"
	@echo "  make test      - Run tests"
	@echo "  make lint      - Static checks (mypy, ruff, import layers)"
	@echo "  make fmt       - Format code"
	@echo "  make coverage  - Tests with a coverage report"

# One command after a clone. Every step is safe to repeat.
dev: install db
	@echo ""
	@echo "ready. 'make test' runs everything, including the database tests."

install:
	uv sync --all-groups

db:
	@test -f .env || cp .env.example .env
	docker compose up -d --wait
	set -a && . ./.env && set +a && \
	  uv run cadence db upgrade --url "$$DATABASE_URL" && \
	  uv run cadence db upgrade --url "$$TEST_DATABASE_URL"

db-down:
	docker compose down

# The database tests need the URLs from .env; without them they skip and the
# suite passes while testing half of what it says it does.
test:
	set -a && [ -f .env ] && . ./.env; set +a; uv run pytest

lint:
	uv run mypy
	uv run ruff check cadence
	uv run lint-imports

fmt:
	uv run ruff format cadence

coverage:
	uv run pytest --cov --cov-report=term-missing
