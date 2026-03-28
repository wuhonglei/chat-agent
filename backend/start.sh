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

echo ""
echo "=========================================="
echo "Starting application server..."
echo "=========================================="

# 获取 CPU 核心数并计算 workers 数量
WORKERS=$(($(nproc) * 2))

# 启动 Gunicorn 应用服务器
exec gunicorn app.main:app -w $WORKERS -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
