#!/bin/bash
set -e

echo "=========================================="
echo "Starting application with auto-migration"
echo "=========================================="

# 等待数据库连接可用（最多等待 60 秒）
echo "Waiting for database connection..."
MAX_RETRIES=60
RETRY_COUNT=0

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    ERROR_OUTPUT=$(uv run alembic current 2>&1)
    if [ $? -eq 0 ]; then
        echo "✓ Database connection established!"
        break
    fi

    RETRY_COUNT=$((RETRY_COUNT + 1))
    if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
        echo "ERROR: Database connection failed after ${MAX_RETRIES} seconds"
        echo "Please check your database configuration and ensure the database is running."
        echo ""
        echo "Last error output:"
        echo "$ERROR_OUTPUT"
        exit 1
    fi

    if [ $((RETRY_COUNT % 5)) -eq 0 ]; then
        echo "Waiting for database... (${RETRY_COUNT}/${MAX_RETRIES})"
        echo "Error: $ERROR_OUTPUT"
    fi
    sleep 1
done

# pgvector + 空库建表 + Alembic（首条迁移仅 alter，空库需 stamp head）
echo ""
echo "Running database setup and migrations..."
uv run python -c "from app.core.migrate_on_deploy import run_deploy_migrations; run_deploy_migrations()"
echo "✓ Database migrations completed successfully"

# 显示当前迁移版本
echo ""
echo "Current migration version:"
uv run alembic current || echo "WARNING: Could not check migration version"

# Prometheus 多进程指标目录（gunicorn --preload 下各 worker 共享）
export PROMETHEUS_MULTIPROC_DIR=/tmp/prometheus_multiproc
rm -rf "$PROMETHEUS_MULTIPROC_DIR"
mkdir -p "$PROMETHEUS_MULTIPROC_DIR"
echo "✓ Prometheus multiproc dir: $PROMETHEUS_MULTIPROC_DIR"

echo ""
echo "=========================================="
echo "Starting application server..."
echo "=========================================="

# Gunicorn workers = 2 * CPU 核数（验证码已迁移到 Redis，可安全多 worker）
WORKERS=$(( $(nproc) * 2 ))

# 启动 Gunicorn 应用服务器
# 注意：不使用 --preload，因为 gRPC 客户端（Nacos）在 fork 后会导致 SIGSEGV
# 每个 worker 独立加载 app，避免 fork 时 gRPC 线程状态不一致
exec gunicorn app.main:app -w $WORKERS -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
