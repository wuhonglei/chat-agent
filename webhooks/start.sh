#!/bin/bash

# Flask 应用启动脚本

set -e

echo "=========================================="
echo "启动时间: $(date)"
echo "=========================================="

# 默认配置
APP_MODULE="main:app"
HOST="0.0.0.0"
PORT="9000"
WORKERS=1
WORKER_CLASS="sync"
LOG_LEVEL="info"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 获取时间戳（loguru 格式）
get_timestamp() {
    date +"[%Y-%m-%d %H:%M:%S %z]"
}

# 打印带颜色的消息
print_message() {
    echo -e "$(get_timestamp) ${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "$(get_timestamp) ${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "$(get_timestamp) ${RED}[ERROR]${NC} $1"
}

# 加载环境变量
load_env() {
    if [ -f ".env" ]; then
        print_message "从 .env 文件加载环境变量..."
        # 使用 set -a 让 export 应用到所有变量
        set -a
        source .env
        set +a
    fi
}

# 检查环境变量
check_env() {
    if [ -z "$WEBHOOK_SECRET" ]; then
        print_error "WEBHOOK_SECRET 环境变量未设置"
        print_error "请在 .env 文件中设置或通过环境变量传入"
        exit 1
    fi

    print_message "环境变量检查通过"
}

# 激活虚拟环境（如果存在）
activate_venv() {
    if [ -d ".venv" ]; then
        print_message "激活虚拟环境..."
        source .venv/bin/activate
    elif [ -d "venv" ]; then
        print_message "激活虚拟环境..."
        source venv/bin/activate
    else
        print_warning "未找到虚拟环境，使用系统 Python"
    fi
}

# 安装依赖
install_deps() {
    print_message "检查并安装依赖..."

    # 检查是否使用 uv
    if command -v uv &> /dev/null; then
        print_message "使用 uv 管理依赖"
        uv sync
    else
        print_warning "未找到 uv，使用 pip"
        pip install -e .
    fi
}

# 启动服务器
start_server() {
    print_message "启动服务器..."

    # 检查 gunicorn 是否已安装
    if ! command -v gunicorn &> /dev/null; then
        print_error "gunicorn 未安装，请运行安装依赖"
        exit 1
    fi

    print_message "使用 Gunicorn 启动，工作进程数: $WORKERS"
    print_message "访问地址: http://$HOST:$PORT"

    exec gunicorn \
        --bind "$HOST:$PORT" \
        --workers "$WORKERS" \
        --worker-class "$WORKER_CLASS" \
        --log-level "$LOG_LEVEL" \
        --access-logfile - \
        --error-logfile - \
        --capture-output \
        "$APP_MODULE"
}

# 显示帮助信息
show_help() {
    cat << EOF
Flask 应用启动脚本

用法:
    $0 [选项]

选项:
    -h, --host HOST          监听主机，默认: 0.0.0.0
    -p, --port PORT          监听端口，默认: 9000
    -w, --workers NUM        Gunicorn 工作进程数，默认: 1
    --install                安装/更新依赖
    --help                   显示此帮助信息

环境变量:
    WEBHOOK_SECRET           Webhook 密钥（必需）
    REPO_PATH               仓库路径，默认: /home/ubuntu/chat-agent
    DEPLOY_SCRIPT           部署脚本路径，默认: /home/ubuntu/chat-agent/deploy.sh
    DEBUG                   调试模式，默认: False

示例:
    # 启动服务器
    $0

    # 自定义端口
    $0 -p 8000

    # 仅安装依赖
    $0 --install

EOF
}

# 解析命令行参数
INSTALL_ONLY=false

while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--host)
            HOST="$2"
            shift 2
            ;;
        -p|--port)
            PORT="$2"
            shift 2
            ;;
        -w|--workers)
            WORKERS="$2"
            shift 2
            ;;
        --install)
            INSTALL_ONLY=true
            shift
            ;;
        --help)
            show_help
            exit 0
            ;;
        *)
            print_error "未知选项: $1"
            show_help
            exit 1
            ;;
    esac
done

# 主逻辑
main() {
    print_message "Flask Webhook 应用启动脚本"

    # 加载环境变量
    load_env

    # 检查环境变量
    check_env

    # 激活虚拟环境
    activate_venv

    # 安装依赖
    if [ "$INSTALL_ONLY" = true ]; then
        install_deps
        print_message "依赖安装完成"
        exit 0
    fi

    install_deps

    # 启动服务
    start_server
}

# 运行主函数
main "$@"
