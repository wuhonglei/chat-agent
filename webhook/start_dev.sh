#!/bin/bash
# 开发环境启动脚本 (使用 Flask 开发服务器)

# 设置环境变量（根据需要修改）
export WEBHOOK_SECRET="${WEBHOOK_SECRET:-your_webhook_secret_here}"
export REPO_PATH="${REPO_PATH:-/home/ubuntu/ai-doc}"
export DEPLOY_SCRIPT="${DEPLOY_SCRIPT:-/home/ubuntu/ai-doc/deploy.sh}"
export DEBUG="${DEBUG:-True}"

echo "启动开发服务器..."
echo "注意：这是开发服务器，不适合生产环境使用！"
echo "生产环境请使用 start.sh (需要先安装 gunicorn)"
echo ""

python3 main.py
