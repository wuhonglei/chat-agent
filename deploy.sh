#!/bin/bash

# 生产环境部署脚本
# 使用方法: ./deploy.sh

set -e

echo "🚀 开始部署 chat-agent 项目..."

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

# 差异部署范围（由 webhook 通过环境变量传入；未设置时默认为 1，兼容直接执行本脚本）
DEPLOY_FRONTEND=${DEPLOY_FRONTEND:-1}
DEPLOY_BACKEND=${DEPLOY_BACKEND:-1}
DEPLOY_EVALUATOR=${DEPLOY_EVALUATOR:-0}

# 零停机部署函数
# 策略：先构建镜像（旧容器继续运行），然后快速切换容器
zero_downtime_deploy() {
    local service=$1
    local max_wait=${2:-120}  # 默认等待 120 秒
    local check_interval=${3:-5}  # 默认每 5 秒检查一次

    echo ""
    echo "🔄 开始更新服务: $service"

    # 检查服务是否需要构建（通过检查 docker-compose.yml 是否有 build 配置）
    local needs_build=false
    if [ -f docker-compose.yml ]; then
        # 检查服务配置块中是否有 build 关键字
        # 从服务名行开始，到下一个服务或文件末尾结束，检查是否有 "build:"
        local service_config=$(sed -n "/^  $service:/,/^  [a-z]/p" docker-compose.yml 2>/dev/null | head -20)
        if echo "$service_config" | grep -q "^    build:"; then
            needs_build=true
        fi
    fi

    # 检查服务是否正在运行
    if ! $DOCKER_COMPOSE_CMD ps | grep -q "$service.*Up"; then
        echo "⚠️  服务 $service 未运行，准备启动..."

        # 检查是否存在已停止的旧容器（可能导致名称冲突）
        local stopped_container=$(docker ps -aq -f name="chat-agent-$service" 2>/dev/null)
        if [ -n "$stopped_container" ]; then
            echo "   发现已停止的旧容器，先清理..."
            docker rm -f "$stopped_container" 2>/dev/null || true
        fi

        # 检查是否存在备份容器
        local backup_containers=$(docker ps -aq --filter "name=chat-agent-$service-backup" 2>/dev/null)
        if [ -n "$backup_containers" ]; then
            echo "   清理旧的备份容器..."
            echo "$backup_containers" | xargs docker rm -f 2>/dev/null || true
        fi

        # 根据是否需要构建来决定命令
        if [ "$needs_build" = true ]; then
            echo "   构建并启动 $service 服务..."
            $DOCKER_COMPOSE_CMD up -d --build --no-deps "$service"
        else
            echo "   启动 $service 服务（使用预定义镜像）..."
            $DOCKER_COMPOSE_CMD up -d --no-deps "$service"
        fi
        return 0
    fi

    # 1. 先构建新镜像（不停止旧容器，这是关键！）
    # 只有需要构建的服务才构建镜像
    if [ "$needs_build" = true ]; then
        echo "🔨 构建 $service 新镜像（旧容器继续运行，服务不中断）..."
        if ! $DOCKER_COMPOSE_CMD build "$service"; then
            echo "❌ $service 镜像构建失败"
            return 1
        fi
    fi

    # 2. 记录旧容器信息和镜像标签（用于回滚）
    local old_container_id=$($DOCKER_COMPOSE_CMD ps -q "$service" 2>/dev/null)
    if [ -z "$old_container_id" ]; then
        old_container_id=$(docker ps -q -f name="^/chat-agent-$service$")
    fi
    local old_image_tag=""
    local old_image_id=""
    local backup_container_name=""
    local compose_project=""
    local compose_service_label=""
    local compose_container_number=""
    local compose_config_hash=""
    if [ -n "$old_container_id" ]; then
        old_image_tag=$(docker inspect "$old_container_id" --format='{{.Config.Image}}' 2>/dev/null || echo "")
        old_image_id=$(docker inspect "$old_container_id" --format='{{.Image}}' 2>/dev/null || echo "")
        compose_project=$(docker inspect "$old_container_id" --format='{{ index .Config.Labels "com.docker.compose.project" }}' 2>/dev/null || echo "")
        compose_service_label=$(docker inspect "$old_container_id" --format='{{ index .Config.Labels "com.docker.compose.service" }}' 2>/dev/null || echo "")
        compose_container_number=$(docker inspect "$old_container_id" --format='{{ index .Config.Labels "com.docker.compose.container-number" }}' 2>/dev/null || echo "")
        compose_config_hash=$(docker inspect "$old_container_id" --format='{{ index .Config.Labels "com.docker.compose.config-hash" }}' 2>/dev/null || echo "")
        echo "   旧容器 ID: $old_container_id"
    fi

    # 3. 启动新容器（先重命名旧容器，以便回滚）
    # 虽然会有短暂停机（通常 1-3 秒），但构建期间服务一直可用
    echo "🚀 启动 $service 新容器（将会有短暂切换时间，通常 1-3 秒）..."

    # 先重命名并停止旧容器（释放端口，保留用于回滚）
    local backup_container_name="chat-agent-$service-backup-$(date +%s)"
    if [ -n "$old_container_id" ]; then
        echo "   备份旧容器为: $backup_container_name"
        docker rename "chat-agent-$service" "$backup_container_name" 2>/dev/null || true
        # 移除 compose 标签，避免 compose 误操作备份容器
        docker container update \
            --label-rm com.docker.compose.project \
            --label-rm com.docker.compose.service \
            --label-rm com.docker.compose.container-number \
            --label-rm com.docker.compose.config-hash \
            --label-rm com.docker.compose.oneoff \
            "$backup_container_name" > /dev/null 2>&1 || true
        docker stop "$backup_container_name" 2>/dev/null || true
    fi

    # 启动新容器
    $DOCKER_COMPOSE_CMD up -d --no-deps --no-build --force-recreate "$service"

    # 4. 等待新容器健康检查通过
    echo "⏳ 等待 $service 健康检查通过（最多等待 ${max_wait} 秒）..."
    local waited=0
    local is_healthy=false
    local new_container_id=""
    local logged_new_container=false

    while [ $waited -lt $max_wait ]; do
        # 检查容器是否在运行
        new_container_id=$($DOCKER_COMPOSE_CMD ps -q "$service" 2>/dev/null)
        if [ -z "$new_container_id" ]; then
            new_container_id=$(docker ps -q -f name="^/chat-agent-$service$")
        fi
        if [ -n "$new_container_id" ]; then
            if [ "$logged_new_container" = false ]; then
                echo "   新容器 ID: $new_container_id"
                logged_new_container=true
            fi
            # 根据服务类型进行健康检查
            if [ "$service" = "backend" ]; then
                if docker exec "$new_container_id" curl -f http://127.0.0.1:8000/ > /dev/null 2>&1; then
                    is_healthy=true
                    break
                fi
            elif [ "$service" = "frontend" ]; then
                # 前端健康检查：从宿主机访问服务
                if curl -f http://localhost:3000/ > /dev/null 2>&1; then
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
        # 清理备份的旧容器
        local backup_containers=$(docker ps -aq --filter "name=chat-agent-$service-backup")
        if [ -n "$backup_containers" ]; then
            echo "   清理备份容器..."
            echo "$backup_containers" | xargs docker rm -f 2>/dev/null || true
        fi
        return 0
    else
        echo "❌ $service 健康检查失败，尝试回滚到旧版本..."
        echo "⚠️  新容器可能存在问题，请检查日志: $DOCKER_COMPOSE_CMD logs $service"

        # 回滚策略：停止新容器，恢复旧容器
        if [ -n "$new_container_id" ]; then
            echo "🔄 停止新容器..."
            docker stop "$new_container_id" 2>/dev/null || true
            docker rm -f "$new_container_id" 2>/dev/null || true
        fi

        # 尝试回滚：查找并恢复备份的旧容器
        echo "🔄 尝试回滚到旧版本..."
        local rollback_success=false

        # 方法1: 查找备份的旧容器（通过名称模式匹配）
        local backup_container=$(docker ps -aq --filter "name=chat-agent-$service-backup" | head -1)
        if [ -z "$backup_container" ]; then
            # 如果没找到，尝试查找所有已停止的容器
            backup_container=$(docker ps -aq --filter "name=chat-agent-$service-backup" --filter "status=exited" | head -1)
        fi

        if [ -n "$backup_container" ]; then
            echo "   发现备份的旧容器，尝试恢复..."
            # 重命名回原来的名称
            docker rename "$backup_container" "chat-agent-$service" 2>/dev/null || true
            # 恢复 compose 标签，确保后续 compose 可识别
            if [ -n "$compose_project" ]; then
                docker container update --label-add "com.docker.compose.project=$compose_project" "chat-agent-$service" > /dev/null 2>&1 || true
            fi
            if [ -n "$compose_service_label" ]; then
                docker container update --label-add "com.docker.compose.service=$compose_service_label" "chat-agent-$service" > /dev/null 2>&1 || true
            fi
            if [ -n "$compose_container_number" ]; then
                docker container update --label-add "com.docker.compose.container-number=$compose_container_number" "chat-agent-$service" > /dev/null 2>&1 || true
            fi
            if [ -n "$compose_config_hash" ]; then
                docker container update --label-add "com.docker.compose.config-hash=$compose_config_hash" "chat-agent-$service" > /dev/null 2>&1 || true
            fi
            # 启动容器
            docker start "chat-agent-$service" 2>/dev/null && sleep 3
            local rollback_container=$(docker ps -q -f name="^/chat-agent-$service$")
            if [ -n "$rollback_container" ]; then
                echo "✅ 已成功回滚到旧容器"
                rollback_success=true
            fi
        fi

        # 方法2: 如果旧容器不存在，尝试使用旧镜像直接启动
        if [ "$rollback_success" = false ] && [ -n "$old_image_id" ] && [ "$old_image_id" != "" ]; then
            echo "   尝试使用旧镜像启动容器..."
            # 获取服务配置信息
            local container_name="chat-agent-$service"
            local network_name="chat-agent-network"

            # 根据服务类型构建启动命令
            if [ "$service" = "backend" ]; then
                docker run -d \
                    --name "$container_name" \
                    --network "$network_name" \
                    -p 8000:8000 \
                    -v "$(pwd)/backend/data:/app/data" \
                    -v "$(pwd)/backend/logs:/app/logs" \
                    --env-file .env \
                    -e DATABASE__HOST=postgres \
                    --restart unless-stopped \
                    "$old_image_id" 2>/dev/null && rollback_success=true
            elif [ "$service" = "frontend" ]; then
                docker run -d \
                    --name "$container_name" \
                    --network "$network_name" \
                    -p 3000:3000 \
                    --restart unless-stopped \
                    "$old_image_id" 2>/dev/null && rollback_success=true
            fi

            if [ "$rollback_success" = true ]; then
                sleep 5
                local rollback_container=$(docker ps -q -f name="^/chat-agent-$service$")
                if [ -n "$rollback_container" ]; then
                    echo "✅ 已使用旧镜像启动容器"
                else
                    rollback_success=false
                fi
            fi
        fi

        # 方法3: 如果以上都失败，尝试使用 docker compose 重新启动（可能使用缓存的旧镜像）
        if [ "$rollback_success" = false ]; then
            echo "   尝试使用 docker compose 重新启动..."
            $DOCKER_COMPOSE_CMD up -d --no-deps --no-build "$service" 2>/dev/null || true
            sleep 5
            local rollback_container=$(docker ps -q -f name="^/chat-agent-$service$")
            if [ -n "$rollback_container" ]; then
                echo "⚠️  容器已启动，但可能使用的是新镜像，请验证服务是否正常"
                rollback_success=true
            fi
        fi

        if [ "$rollback_success" = true ]; then
            echo "⚠️  回滚完成，但服务可能不稳定"
            echo "💡 建议立即检查并修复问题："
            echo "   查看日志: $DOCKER_COMPOSE_CMD logs $service"
            echo "   检查状态: docker ps | grep $service"
            return 1
        else
            echo "❌ 回滚失败，服务 $service 当前不可用"
            echo "💡 请手动检查并修复问题："
            echo "   查看日志: $DOCKER_COMPOSE_CMD logs $service"
            echo "   手动重启: $DOCKER_COMPOSE_CMD restart $service"
            echo "   或使用旧镜像手动启动: docker run ..."
            return 1
        fi
    fi
}

# 检查是否是首次部署（没有运行中的容器）
IS_FIRST_DEPLOY=false
if ! $DOCKER_COMPOSE_CMD ps | grep -q "Up"; then
    IS_FIRST_DEPLOY=true
    echo "📦 检测到首次部署，将直接启动所有服务..."
fi

if [ "$IS_FIRST_DEPLOY" = true ]; then
    # 首次部署：清理已停止的旧容器，然后按 DEPLOY_BACKEND / DEPLOY_FRONTEND 构建并启动（与 webhook 增量逻辑一致）
    echo "🧹 清理已停止的旧容器..."

    # 清理所有项目相关的已停止容器
    for service in postgres backend frontend evaluator; do
        stopped_container=$(docker ps -aq -f name="chat-agent-$service" 2>/dev/null)
        if [ -n "$stopped_container" ]; then
            echo "   清理已停止的 $service 容器..."
            docker rm -f "$stopped_container" 2>/dev/null || true
        fi

        # 清理备份容器
        backup_containers=$(docker ps -aq --filter "name=chat-agent-$service-backup" 2>/dev/null)
        if [ -n "$backup_containers" ]; then
            echo "   清理 $service 的备份容器..."
            echo "$backup_containers" | xargs docker rm -f 2>/dev/null || true
        fi
    done

    first_compose_services=()
    if [ "$DEPLOY_BACKEND" = "1" ] || [ "$DEPLOY_FRONTEND" = "1" ]; then
        first_compose_services+=(postgres)
    fi
    if [ "$DEPLOY_BACKEND" = "1" ]; then
        first_compose_services+=(backend)
    elif [ "$DEPLOY_FRONTEND" = "1" ]; then
        # compose 中 frontend depends_on backend，仅部署前端时仍需拉起 backend
        first_compose_services+=(backend)
    fi
    if [ "$DEPLOY_FRONTEND" = "1" ]; then
        first_compose_services+=(frontend)
    fi
    if [ "$DEPLOY_EVALUATOR" = "1" ]; then
        # evaluator depends_on postgres + backend
        if [[ ! " ${first_compose_services[*]} " =~ " postgres " ]]; then
            first_compose_services+=(postgres)
        fi
        if [[ ! " ${first_compose_services[*]} " =~ " backend " ]]; then
            first_compose_services+=(backend)
        fi
        first_compose_services+=(evaluator)
    fi

    if [ ${#first_compose_services[@]} -eq 0 ]; then
        echo "⚠️  DEPLOY_BACKEND、DEPLOY_FRONTEND 与 DEPLOY_EVALUATOR 均为 0，跳过 postgres / backend / frontend / evaluator 启动"
    else
        echo "🔨 首次部署：构建并启动服务（范围: backend=$DEPLOY_BACKEND, frontend=$DEPLOY_FRONTEND, evaluator=$DEPLOY_EVALUATOR）..."
        echo "   服务列表: ${first_compose_services[*]}"
        # --wait + --wait-timeout：depends_on service_healthy 时默认约 60s 会放弃；后端冷启动常超过该时间
        if $DOCKER_COMPOSE_CMD up --help 2>&1 | grep -qF 'wait-timeout'; then
            $DOCKER_COMPOSE_CMD up -d --build --wait --wait-timeout 300 "${first_compose_services[@]}"
        else
            $DOCKER_COMPOSE_CMD up -d --build "${first_compose_services[@]}"
        fi
    fi
else
    # 更新部署：按 DEPLOY_BACKEND / DEPLOY_FRONTEND 差异更新（postgres 仅首次部署时启动，此处不更新）
    echo "🔄 开始零停机部署更新（范围: backend=$DEPLOY_BACKEND, frontend=$DEPLOY_FRONTEND, evaluator=$DEPLOY_EVALUATOR）..."

    BACKEND_DEPLOY_SUCCESS=true
    FRONTEND_DEPLOY_SUCCESS=true

    if [ "$DEPLOY_BACKEND" = "1" ]; then
        if ! zero_downtime_deploy "backend" 120; then
            echo "❌ 后端服务更新失败"
            BACKEND_DEPLOY_SUCCESS=false
        fi
    else
        echo "⏭️  跳过 backend 更新（无相关变更）"
    fi

    if [ "$DEPLOY_FRONTEND" = "1" ]; then
        if ! zero_downtime_deploy "frontend" 90; then
            echo "❌ 前端服务更新失败"
            FRONTEND_DEPLOY_SUCCESS=false
        fi
    else
        echo "⏭️  跳过 frontend 更新（无相关变更）"
    fi

    EVALUATOR_DEPLOY_SUCCESS=true
    if [ "$DEPLOY_EVALUATOR" = "1" ]; then
        if ! zero_downtime_deploy "evaluator" 120; then
            echo "❌ evaluator 服务更新失败"
            EVALUATOR_DEPLOY_SUCCESS=false
        fi
    else
        echo "⏭️  跳过 evaluator 更新（无相关变更）"
    fi

    # 如果本次需要更新的服务全部失败，则退出
    if [ "$BACKEND_DEPLOY_SUCCESS" = false ] && [ "$FRONTEND_DEPLOY_SUCCESS" = false ] && [ "$EVALUATOR_DEPLOY_SUCCESS" = false ]; then
        echo "❌ 所有待更新服务部署失败，部署中止"
        exit 1
    fi

    if [ "$BACKEND_DEPLOY_SUCCESS" = false ] || [ "$FRONTEND_DEPLOY_SUCCESS" = false ] || [ "$EVALUATOR_DEPLOY_SUCCESS" = false ]; then
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

# 最终健康检查（与本次部署范围一致，避免仅更后端却因未起前端而误判失败）
echo ""
echo "🏥 执行最终健康检查..."
ALL_HEALTHY=true

need_backend_check=false
need_postgres_check=false
if [ "$DEPLOY_BACKEND" = "1" ] || [ "$DEPLOY_FRONTEND" = "1" ]; then
    need_backend_check=true
    need_postgres_check=true
fi

if [ "$need_postgres_check" = true ]; then
    if $DOCKER_COMPOSE_CMD exec -T postgres pg_isready -U ${PG_USER_NAME:-postgres} > /dev/null 2>&1; then
        echo "✅ 数据库服务运行正常"
    else
        echo "❌ 数据库服务健康检查失败"
        ALL_HEALTHY=false
    fi
fi

if [ "$need_backend_check" = true ]; then
    if $DOCKER_COMPOSE_CMD exec -T backend curl -f http://127.0.0.1:8000/ > /dev/null 2>&1; then
        echo "✅ 后端服务运行正常"
    else
        echo "❌ 后端服务健康检查失败"
        ALL_HEALTHY=false
    fi
fi

if [ "$DEPLOY_FRONTEND" = "1" ]; then
    if curl -f http://localhost:3000/ > /dev/null 2>&1; then
        echo "✅ 前端服务运行正常"
    else
        echo "❌ 前端服务健康检查失败"
        ALL_HEALTHY=false
    fi
fi

if [ "$DEPLOY_EVALUATOR" = "1" ]; then
    evaluator_container=$(docker ps -q -f name="^/chat-agent-evaluator$" 2>/dev/null)
    if [ -n "$evaluator_container" ]; then
        echo "✅ evaluator 服务运行正常"
    else
        echo "❌ evaluator 服务健康检查失败"
        ALL_HEALTHY=false
    fi
fi

echo ""
if [ "$ALL_HEALTHY" = true ]; then
    echo "✅ 部署完成！所有服务运行正常"
else
    echo "⚠️  部署完成，但部分服务可能存在问题，请检查日志"
fi

# 镜像清理功能
# 可以通过环境变量 CLEANUP_IMAGES=true 来启用，或设置为 false 来禁用
# 默认：如果所有服务健康，则清理；否则不清理（保留用于调试）
CLEANUP_IMAGES=${CLEANUP_IMAGES:-"auto"}

if [ "$CLEANUP_IMAGES" = "true" ] || ([ "$CLEANUP_IMAGES" = "auto" ] && [ "$ALL_HEALTHY" = true ]); then
    echo ""
    echo "🧹 开始清理未使用的 Docker 镜像..."

    # 1. 清理 dangling 镜像（构建过程中产生的未标记镜像）
    echo "   清理 dangling 镜像..."
    dangling_before=$(docker images -f "dangling=true" -q 2>/dev/null | wc -l | tr -d ' ')
    if [ "$dangling_before" -gt 0 ]; then
        docker image prune -f > /dev/null 2>&1 || true
        echo "   ✅ 已清理 dangling 镜像"
    else
        echo "   ℹ️  没有 dangling 镜像需要清理"
    fi

    # 2. 清理未使用的镜像（使用 Docker 内置命令，安全可靠）
    # 注意：docker image prune -a 会删除所有未使用的镜像，包括其他项目的
    # 为了安全，我们只清理明确未使用的镜像，不强制删除
    echo "   检查未使用的镜像..."

    # 获取当前使用的镜像 ID（包括运行中的容器和备份容器）
    used_image_ids=""
    for service in backend frontend evaluator; do
        # 运行中的容器
        container_id=$(docker ps -q -f name="^/chat-agent-$service$" 2>/dev/null)
        if [ -n "$container_id" ]; then
            image_id=$(docker inspect "$container_id" --format='{{.Image}}' 2>/dev/null || echo "")
            if [ -n "$image_id" ]; then
                used_image_ids="$used_image_ids|$image_id"
            fi
        fi
        # 备份容器（可能用于回滚）
        backup_containers=$(docker ps -aq --filter "name=chat-agent-$service-backup" 2>/dev/null)
        if [ -n "$backup_containers" ]; then
            for backup_id in $backup_containers; do
                image_id=$(docker inspect "$backup_id" --format='{{.Image}}' 2>/dev/null || echo "")
                if [ -n "$image_id" ]; then
                    used_image_ids="$used_image_ids|$image_id"
                fi
            done
        fi
    done

    # 清理未使用的镜像（但保留最近 24 小时内的，用于回滚）
    # 使用 --filter "until=24h" 只清理 24 小时前未使用的镜像
    echo "   清理 24 小时前未使用的镜像（保留最近版本用于回滚）..."
    prune_output=$(docker image prune -a -f --filter "until=24h" 2>&1 || echo "")

    if echo "$prune_output" | grep -q "Total reclaimed space"; then
        space_reclaimed=$(echo "$prune_output" | grep -oP "Total reclaimed space: \K[0-9.]+[A-Z]+" || echo "")
        echo "   ✅ 已清理未使用的镜像，释放空间: $space_reclaimed"
    else
        echo "   ℹ️  没有需要清理的旧镜像（所有镜像都在使用中或最近 24 小时内）"
    fi

    echo "✅ 镜像清理完成"
    echo ""
    echo "💡 提示：可以通过设置环境变量来控制清理行为："
    echo "   CLEANUP_IMAGES=true   - 强制清理"
    echo "   CLEANUP_IMAGES=false  - 不清理"
    echo "   CLEANUP_IMAGES=auto   - 自动（默认：服务健康时清理）"
    echo ""
    echo "   查看磁盘使用: docker system df"
    echo "   手动清理所有未使用镜像: docker image prune -a"
    echo "   查看镜像列表: docker images"
elif [ "$CLEANUP_IMAGES" = "false" ]; then
    echo ""
    echo "ℹ️  跳过镜像清理（CLEANUP_IMAGES=false）"
fi

echo ""
echo "📋 常用命令："
echo "  查看日志: $DOCKER_COMPOSE_CMD logs -f"
echo "  查看特定服务日志: $DOCKER_COMPOSE_CMD logs -f backend"
echo "  停止服务: $DOCKER_COMPOSE_CMD down"
echo "  重启服务: $DOCKER_COMPOSE_CMD restart"
echo "  查看服务状态: $DOCKER_COMPOSE_CMD ps"
echo "  查看镜像: docker images"
echo "  手动清理镜像: docker image prune -a"
