#!/bin/bash
# 生产环境启动脚本 (使用 Gunicorn)

# 检查是否安装了 gunicorn
if ! command -v gunicorn &> /dev/null; then
    echo "错误：未找到 gunicorn。请先安装：pip install gunicorn"
    exit 1
fi

# 设置环境变量（根据需要修改）
export WEBHOOK_SECRET="${WEBHOOK_SECRET:-your_webhook_secret_here}"
export REPO_PATH="${REPO_PATH:-/home/ubuntu/ai-doc}"
export DEPLOY_SCRIPT="${DEPLOY_SCRIPT:-/home/ubuntu/ai-doc/deploy.sh}"
export DEBUG="${DEBUG:-False}"

# 使用 gunicorn 启动应用
# 参数说明：
# -w 4: 4个工作进程
# --bind 0.0.0.0:9000: 绑定地址和端口
# --access-logfile -: 访问日志输出到 stdout
# --error-logfile -: 错误日志输出到 stderr
# main:app: 应用模块和应用实例

echo "启动生产服务器..."
exec gunicorn -w 4 --bind 0.0.0.0:9000 \
    --access-logfile - \
    --error-logfile - \
    --log-level info \
    main:app