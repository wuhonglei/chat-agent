.PHONY: format lint check install dev clean help

# Default target
help:
	@echo "Available commands:"
	@echo "  format     - Format code with ruff and black"
	@echo "  lint       - Run linting checks"
	@echo "  check      - Run type checking with mypy"
	@echo "  install    - Install dependencies"
	@echo "  dev        - Install with dev dependencies"
	@echo "  clean      - Clean temporary files"
	@echo "  test       - Run tests"
	@echo "  start      - Start the application"

# Install dependencies
install:
	uv sync

# Install with dev dependencies
dev:
	uv sync --extra dev

# Format code
format:
	python format.py

# Quick format using individual tools
format-ruff:
	python -m ruff check --fix app/
	python -m ruff format app/

format-black:
	python -m black app/

# Linting
lint:
	python -m ruff check app/

# Type checking
check:
	python -m mypy app/

# Run tests
test:
	python -m pytest

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

# Start the application
start:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000