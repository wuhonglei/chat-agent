.PHONY: format lint check install dev start stop clean help migrate

# Default target
help:
	@echo "Available commands:"
	@echo "  format     - Format code with ruff"
	@echo "  lint       - Run linting checks"
	@echo "  check      - Run type checking with mypy"
	@echo "  install    - Install dependencies"
	@echo "  dev        - Start the application (reload, debug)"
	@echo "  start      - Start the application (multi-worker)"
	@echo "  stop       - Stop process listening on port 8000 (dev/start)"
	@echo "  migrate    - Run database migrations (alembic upgrade head)"
	@echo "  clean      - Clean temporary files"
	@echo "  test       - Run tests"

# Install dependencies
install:
	uv sync --extra dev --group dev

# Start the application (python -m uvicorn avoids picking up a global/Homebrew uvicorn on PATH)
dev:
	APP__DEBUG=1 uv run python -m uvicorn app.main:app --reload --reload-dir app --host 0.0.0.0 --port 8000 --proxy-headers

# Start the application
start:
	uv run python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4 --log-level info --proxy-headers

# Stop dev/start (same port as above)
stop:
	@PIDS=$$(lsof -tiTCP:8000 -sTCP:LISTEN 2>/dev/null || true); \
	if [ -n "$$PIDS" ]; then \
		echo "SIGTERM PID(s) on :8000: $$PIDS"; \
		kill -TERM $$PIDS 2>/dev/null || true; \
		sleep 1; \
		PIDS2=$$(lsof -tiTCP:8000 -sTCP:LISTEN 2>/dev/null || true); \
		if [ -n "$$PIDS2" ]; then \
			echo "SIGKILL PID(s) still on :8000: $$PIDS2"; \
			kill -KILL $$PIDS2 2>/dev/null || true; \
		fi; \
	else \
		echo "No process listening on TCP port 8000."; \
	fi

# Run database migrations
migrate:
	uv run alembic upgrade head

# Format code
format:
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
