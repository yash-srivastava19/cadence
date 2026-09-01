.PHONY: install test lint fmt help

help:
	@echo "cadence — LLM-based program evolution"
	@echo ""
	@echo "Quick start:"
	@echo "  make install   - Setup (one-time, ~30s)"
	@echo "  make test      - Run tests"
	@echo "  make lint      - Run linting"
	@echo "  make fmt       - Format code"

install:
	uv sync --all-groups

test:
	uv run pytest

lint:
	uv run mypy cadence
	uv run ruff check cadence

fmt:
	uv run ruff format cadence
