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
    if uv run alembic current &>/dev/null; then
        echo "✓ Database connection established!"
        break
    fi
    
    RETRY_COUNT=$((RETRY_COUNT + 1))
    if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
        echo "ERROR: Database connection failed after ${MAX_RETRIES} seconds"
        echo "Please check your database configuration and ensure the database is running."
        exit 1
    fi
    
    if [ $((RETRY_COUNT % 5)) -eq 0 ]; then
        echo "Waiting for database... (${RETRY_COUNT}/${MAX_RETRIES})"
    fi
    sleep 1
done

# 执行数据库迁移
echo ""
echo "Running database migrations..."
if uv run alembic upgrade head; then
    echo "✓ Database migrations completed successfully"
else
    echo "WARNING: Database migration encountered issues, but continuing..."
    echo "You may need to manually check and fix migration issues."
fi

# 显示当前迁移版本
echo ""
echo "Current migration version:"
uv run alembic current || echo "WARNING: Could not check migration version"

echo ""
echo "=========================================="
echo "Starting application server..."
echo "=========================================="

# 启动应用
exec uvicorn app.main:app --host 0.0.0.0 --port 8000

