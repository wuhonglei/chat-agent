#!/bin/bash

# 生产环境部署脚本
# 使用方法: ./deploy.sh

set -e

echo "🚀 开始部署 AI-Doc 项目..."

# 检查 Docker 是否安装
if ! command -v docker &> /dev/null; then
    echo "📦 Docker 未安装，正在安装 Docker..."
    
    # 检测操作系统类型
    if [ -f /etc/redhat-release ]; then
        # CentOS/RHEL 系统
        echo "检测到 CentOS/RHEL 系统，开始安装 Docker..."
        
        # 安装必要的工具
        sudo yum install -y yum-utils
        
        # 添加 Docker 官方仓库
        sudo yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
        
        # 安装 Docker 引擎
        sudo yum install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
        
        # 启动 Docker 服务
        sudo systemctl start docker
        sudo systemctl enable docker
        
        echo "✅ Docker 安装完成"
    elif [ -f /etc/debian_version ]; then
        # Debian/Ubuntu 系统
        echo "检测到 Debian/Ubuntu 系统，开始安装 Docker..."
        
        # 更新包索引
        sudo apt-get update
        
        # 安装必要的工具
        sudo apt-get install -y ca-certificates curl gnupg lsb-release
        
        # 添加 Docker 官方 GPG 密钥
        sudo mkdir -p /etc/apt/keyrings
        curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
        
        # 添加 Docker 官方仓库
        echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
        
        # 安装 Docker 引擎
        sudo apt-get update
        sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
        
        # 启动 Docker 服务
        sudo systemctl start docker
        sudo systemctl enable docker
        
        echo "✅ Docker 安装完成"
    else
        echo "❌ 不支持的操作系统，请手动安装 Docker"
        echo "参考: https://docs.docker.com/engine/install/"
        exit 1
    fi
    
    # 验证安装
    if ! command -v docker &> /dev/null; then
        echo "❌ Docker 安装失败，请检查错误信息"
        exit 1
    fi
fi

# 检查 Docker Compose 是否可用（支持新版本 docker compose 和旧版本 docker-compose）
DOCKER_COMPOSE_CMD=""
if docker compose version &> /dev/null; then
    # 新版本：docker compose (plugin)
    DOCKER_COMPOSE_CMD="docker compose"
    echo "✅ 检测到 Docker Compose Plugin (docker compose)"
elif command -v docker-compose &> /dev/null; then
    # 旧版本：docker-compose (standalone)
    DOCKER_COMPOSE_CMD="docker-compose"
    echo "✅ 检测到 Docker Compose Standalone (docker-compose)"
else
    echo "❌ Docker Compose 未安装"
    echo "如果已安装 docker-compose-plugin，请确保 Docker 版本 >= 20.10"
    echo "否则请手动安装: https://docs.docker.com/compose/install/"
    exit 1
fi

# 检查环境变量文件
if [ ! -f .env ]; then
    echo "⚠️  未找到 .env 文件，正在从示例文件创建..."
    if [ -f docker-compose.env.example ]; then
        cp docker-compose.env.example .env
        echo "✅ 已创建 .env 文件，请编辑后重新运行此脚本"
        exit 1
    else
        echo "❌ 未找到 docker-compose.env.example 文件"
        exit 1
    fi
fi

# 停止现有容器
echo "🛑 停止现有容器..."
$DOCKER_COMPOSE_CMD down

# 构建并启动服务
echo "🔨 构建并启动服务..."
$DOCKER_COMPOSE_CMD up -d --build

# 等待服务启动
echo "⏳ 等待服务启动..."
sleep 10

# 检查服务状态
echo "📊 检查服务状态..."
$DOCKER_COMPOSE_CMD ps

# 检查健康状态
echo "🏥 检查服务健康状态..."
if $DOCKER_COMPOSE_CMD exec -T backend curl -f http://localhost:8000/ > /dev/null 2>&1; then
    echo "✅ 后端服务运行正常"
else
    echo "⚠️  后端服务可能未就绪，请检查日志: $DOCKER_COMPOSE_CMD logs backend"
fi

echo ""
echo "✅ 部署完成！"
echo ""
echo "📋 常用命令："
echo "  查看日志: $DOCKER_COMPOSE_CMD logs -f"
echo "  停止服务: $DOCKER_COMPOSE_CMD down"
echo "  重启服务: $DOCKER_COMPOSE_CMD restart"

