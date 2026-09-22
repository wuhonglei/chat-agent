.PHONY: format lint check install dev start stop clean help migrate eval-gate nacos-tunnel

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

# Ensure SSH tunnel to Nacos (1.12.53.9) is up; idempotent
nacos-tunnel:
	@if lsof -tiTCP:8848 -sTCP:LISTEN >/dev/null 2>&1; then \
		echo "nacos tunnel already up (localhost:8848)"; \
	else \
		echo "starting nacos ssh tunnel..."; \
		ssh -f -N -L 8848:127.0.0.1:8848 -L 9848:127.0.0.1:9848 ubuntu@1.12.53.9; \
		sleep 1; \
		lsof -tiTCP:8848 -sTCP:LISTEN >/dev/null 2>&1 && echo "tunnel up" || (echo "tunnel FAILED"; exit 1); \
	fi

# Start the application (python -m uvicorn avoids picking up a global/Homebrew uvicorn on PATH)
dev: nacos-tunnel
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

# Linting（含两个常驻 worker 包：它们与 backend 同镜像，同样要过 lint/type check）
lint:
	uv run ruff check app/ memory_worker/ eval_worker/

# Type checking
check:
	uv run mypy app/ memory_worker/ eval_worker/

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

# CI eval gate: run eval set, fail if scores drop below thresholds
eval-gate:
	uv run python scripts/run_eval_gate.py

# CI eval gate (replay mode): regenerate answers via real API, then judge
eval-gate-replay:
	uv run python scripts/run_eval_gate.py --replay
