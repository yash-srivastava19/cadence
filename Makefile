.PHONY: install test lint fmt help

help:
	@echo "cadence — LLM-based program evolution"
	@echo ""
	@echo "Quick start:"
	@echo "  make install   - Setup (one-time, ~30s)"
	@echo "  make test      - Run tests"
	@echo "  make lint      - Static checks (mypy, ruff, import layers)"
	@echo "  make fmt       - Format code"
	@echo "  make coverage  - Tests with a coverage report"

install:
	uv sync --all-groups

test:
	uv run pytest

lint:
	uv run mypy
	uv run ruff check cadence
	uv run lint-imports

fmt:
	uv run ruff format cadence

coverage:
	uv run pytest --cov --cov-report=term-missing
