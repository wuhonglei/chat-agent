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

# 零停机部署函数
# 策略：先构建镜像（旧容器继续运行），然后快速切换容器
zero_downtime_deploy() {
    local service=$1
    local max_wait=${2:-120}  # 默认等待 120 秒
    local check_interval=${3:-5}  # 默认每 5 秒检查一次
    
    echo ""
    echo "🔄 开始更新服务: $service"
    
    # 检查服务是否正在运行
    if ! $DOCKER_COMPOSE_CMD ps | grep -q "$service.*Up"; then
        echo "⚠️  服务 $service 未运行，直接启动..."
        $DOCKER_COMPOSE_CMD up -d --build --no-deps "$service"
        return 0
    fi
    
    # 1. 先构建新镜像（不停止旧容器，这是关键！）
    echo "🔨 构建 $service 新镜像（旧容器继续运行，服务不中断）..."
    $DOCKER_COMPOSE_CMD build "$service"
    
    if [ $? -ne 0 ]; then
        echo "❌ $service 镜像构建失败"
        return 1
    fi
    
    # 2. 记录旧容器信息和镜像标签（用于回滚）
    local old_container_id=$(docker ps -q -f name="ai-doc-$service")
    local old_image_tag=""
    if [ -n "$old_container_id" ]; then
        old_image_tag=$(docker inspect "$old_container_id" --format='{{.Config.Image}}' 2>/dev/null || echo "")
    fi
    
    # 3. 启动新容器（docker compose 会先停止旧容器再启动新容器）
    # 虽然会有短暂停机（通常 1-3 秒），但构建期间服务一直可用
    echo "🚀 启动 $service 新容器（将会有短暂切换时间，通常 1-3 秒）..."
    $DOCKER_COMPOSE_CMD up -d --no-deps --force-recreate --no-build "$service"
    
    # 4. 等待新容器健康检查通过
    echo "⏳ 等待 $service 健康检查通过（最多等待 ${max_wait} 秒）..."
    local waited=0
    local is_healthy=false
    local new_container_id=""
    
    while [ $waited -lt $max_wait ]; do
        # 检查容器是否在运行
        new_container_id=$(docker ps -q -f name="ai-doc-$service")
        if [ -n "$new_container_id" ]; then
            # 根据服务类型进行健康检查
            if [ "$service" = "backend" ]; then
                if docker exec "$new_container_id" curl -f http://localhost:8000/ > /dev/null 2>&1; then
                    is_healthy=true
                    break
                fi
            elif [ "$service" = "frontend" ]; then
                # 前端健康检查：检查容器进程
                if docker exec "$new_container_id" ps aux | grep -qE "node|next"; then
                    is_healthy=true
                    break
                fi
            elif [ "$service" = "postgres" ]; then
                # 数据库健康检查
                if docker exec "$new_container_id" pg_isready -U ${PG_USER_NAME:-postgres} > /dev/null 2>&1; then
                    is_healthy=true
                    break
                fi
            else
                # 默认：只要容器运行就认为健康
                is_healthy=true
                break
            fi
        fi
        
        sleep $check_interval
        waited=$((waited + check_interval))
        echo "   等待中... (${waited}/${max_wait} 秒)"
    done
    
    if [ "$is_healthy" = true ]; then
        echo "✅ $service 更新成功并已就绪"
        # 清理旧容器（如果还在）
        if [ -n "$old_container_id" ] && [ "$old_container_id" != "$new_container_id" ]; then
            docker rm -f "$old_container_id" 2>/dev/null || true
        fi
        return 0
    else
        echo "❌ $service 健康检查失败，尝试回滚到旧版本..."
        echo "⚠️  新容器可能存在问题，请检查日志: $DOCKER_COMPOSE_CMD logs $service"
        
        # 回滚策略：停止新容器，尝试恢复旧容器
        if [ -n "$new_container_id" ]; then
            echo "🔄 停止新容器..."
            docker stop "$new_container_id" 2>/dev/null || true
            docker rm -f "$new_container_id" 2>/dev/null || true
        fi
        
        # 尝试使用旧镜像重新启动（如果有旧镜像标签）
        if [ -n "$old_image_tag" ] && [ "$old_image_tag" != "" ]; then
            echo "🔄 尝试使用旧镜像恢复服务..."
            # 使用 docker compose 重新启动，这可能会使用旧镜像
            $DOCKER_COMPOSE_CMD up -d --no-deps --no-build "$service" 2>/dev/null || true
            sleep 5
            local rollback_container=$(docker ps -q -f name="ai-doc-$service")
            if [ -n "$rollback_container" ]; then
                echo "⚠️  已回滚到旧版本，但旧容器可能无法正常恢复"
                echo "💡 建议手动检查并修复问题："
                echo "   查看日志: $DOCKER_COMPOSE_CMD logs $service"
                echo "   手动重启: $DOCKER_COMPOSE_CMD restart $service"
                return 1
            fi
        fi
        
        echo "❌ 回滚失败，服务 $service 当前不可用"
        echo "💡 请手动检查并修复问题："
        echo "   查看日志: $DOCKER_COMPOSE_CMD logs $service"
        echo "   手动重启: $DOCKER_COMPOSE_CMD restart $service"
        return 1
    fi
}

# 检查是否是首次部署（没有运行中的容器）
IS_FIRST_DEPLOY=false
if ! $DOCKER_COMPOSE_CMD ps | grep -q "Up"; then
    IS_FIRST_DEPLOY=true
    echo "📦 检测到首次部署，将直接启动所有服务..."
fi

if [ "$IS_FIRST_DEPLOY" = true ]; then
    # 首次部署：直接构建并启动所有服务
    echo "🔨 构建并启动所有服务..."
    $DOCKER_COMPOSE_CMD up -d --build
else
    # 更新部署：零停机更新
    echo "🔄 开始零停机部署更新..."
    
    # 按依赖顺序更新服务：postgres -> backend -> frontend
    # 注意：数据库通常不需要频繁更新，但为了完整性包含在内
    
    # 更新 postgres（如果需要）
    # zero_downtime_deploy "postgres" 60
    
    # 更新 backend
    BACKEND_DEPLOY_SUCCESS=true
    if ! zero_downtime_deploy "backend" 120; then
        echo "❌ 后端服务更新失败"
        BACKEND_DEPLOY_SUCCESS=false
    fi
    
    # 更新 frontend
    FRONTEND_DEPLOY_SUCCESS=true
    if ! zero_downtime_deploy "frontend" 90; then
        echo "❌ 前端服务更新失败"
        FRONTEND_DEPLOY_SUCCESS=false
    fi
    
    # 如果所有服务都失败，则退出
    if [ "$BACKEND_DEPLOY_SUCCESS" = false ] && [ "$FRONTEND_DEPLOY_SUCCESS" = false ]; then
        echo "❌ 所有服务部署失败，部署中止"
        exit 1
    fi
    
    # 如果有部分服务失败，继续执行但不退出，让用户知道状态
    if [ "$BACKEND_DEPLOY_SUCCESS" = false ] || [ "$FRONTEND_DEPLOY_SUCCESS" = false ]; then
        echo ""
        echo "⚠️  部分服务部署失败，但继续检查整体状态..."
    fi
fi

# 等待所有服务稳定
echo ""
echo "⏳ 等待所有服务稳定..."
sleep 5

# 检查服务状态
echo "📊 检查服务状态..."
$DOCKER_COMPOSE_CMD ps

# 最终健康检查
echo ""
echo "🏥 执行最终健康检查..."
ALL_HEALTHY=true

if $DOCKER_COMPOSE_CMD exec -T backend curl -f http://localhost:8000/ > /dev/null 2>&1; then
    echo "✅ 后端服务运行正常"
else
    echo "❌ 后端服务健康检查失败"
    ALL_HEALTHY=false
fi

if $DOCKER_COMPOSE_CMD ps | grep -q "frontend.*Up"; then
    echo "✅ 前端服务运行正常"
else
    echo "❌ 前端服务未运行"
    ALL_HEALTHY=false
fi

if $DOCKER_COMPOSE_CMD exec -T postgres pg_isready -U ${PG_USER_NAME:-postgres} > /dev/null 2>&1; then
    echo "✅ 数据库服务运行正常"
else
    echo "❌ 数据库服务健康检查失败"
    ALL_HEALTHY=false
fi

echo ""
if [ "$ALL_HEALTHY" = true ]; then
    echo "✅ 部署完成！所有服务运行正常"
else
    echo "⚠️  部署完成，但部分服务可能存在问题，请检查日志"
fi
echo ""
echo "📋 常用命令："
echo "  查看日志: $DOCKER_COMPOSE_CMD logs -f"
echo "  查看特定服务日志: $DOCKER_COMPOSE_CMD logs -f backend"
echo "  停止服务: $DOCKER_COMPOSE_CMD down"
echo "  重启服务: $DOCKER_COMPOSE_CMD restart"
echo "  查看服务状态: $DOCKER_COMPOSE_CMD ps"
