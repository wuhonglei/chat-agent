.PHONY: format lint check install dev clean help

# Default target
help:
	@echo "Available commands:"
	@echo "  format     - Format code with ruff"
	@echo "  lint       - Run linting checks"
	@echo "  check      - Run type checking with mypy"
	@echo "  install    - Install dependencies"
	@echo "  dev        - Start the application"
	@echo "  start      - Start the application"
	@echo "  clean      - Clean temporary files"
	@echo "  test       - Run tests"

# Install dependencies
install:
	uv sync --extra dev --group dev

# Start the application
dev:
	APP__DEBUG=1 uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 --proxy-headers

# Start the application
start:
	uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4 --log-level info --proxy-headers

# Format code
format:
	uv run format.py

# Quick format using ruff
format-ruff:
	uv run ruff check --fix app/
	uv run ruff format app/

# Linting
lint:
	uv run ruff check app/

# Type checking
check:
	uv run mypy app/

# Run tests
test:
	uv run pytest

# Clean temporary files
clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +
	find . -type d -name ".ruff_cache" -exec rm -rf {} +

# All checks (format, lint, type check)
all: format lint check
