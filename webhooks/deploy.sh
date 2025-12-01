#!/bin/bash

# AI-Doc 部署脚本
# 用于在服务器上部署应用

set -e  # 遇到错误立即退出

echo "=========================================="
echo "开始部署 AI-Doc 应用"
echo "时间: $(date)"
echo "=========================================="

# 切换到项目目录（如果需要）
# cd /path/to/your/project

echo "[1/4] 激活虚拟环境..."
if [ -d ".venv" ]; then
    source .venv/bin/activate
elif [ -d "venv" ]; then
    source venv/bin/activate
else
    echo "警告: 未找到虚拟环境，使用系统 Python"
fi

echo "[2/4] 安装/更新依赖..."
if command -v uv &> /dev/null; then
    echo "使用 uv 管理依赖..."
    uv sync
else
    echo "使用 pip 安装依赖..."
    pip install -e .
fi

echo "[3/4] 运行数据库迁移（如果需要）..."
# 如果有数据库迁移命令，请在这里添加
# python manage.py migrate

echo "[4/4] 重启应用服务..."
# 如果需要重启服务，请在这里添加
# systemctl restart your-service
# 或者使用进程管理器重启

echo "=========================================="
echo "部署完成！"
echo "时间: $(date)"
echo "=========================================="

# 可选：发送通知
# curl -X POST -H 'Content-type: application/json' \
#      --data '{"text":"部署完成"}' \
#      YOUR_SLACK_WEBHOOK_URL
