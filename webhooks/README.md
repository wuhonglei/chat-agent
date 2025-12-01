# Webhook for GitHub

## push 测试
1
2
3
4
5
6
7
8
9

## 概述

这是一个基于 GitHub Webhook 的部署脚本，用于自动部署代码到服务器。当在 main 分支上创建标签时，会自动触发部署流程。

## 配置

### 1. 环境变量配置

复制 `.env.example` 为 `.env` 并填入实际值：

```bash
cp .env.example .env
```

编辑 `.env` 文件，设置以下环境变量：

- `WEBHOOK_SECRET`: GitHub Webhook 的 Secret（必须设置，与 GitHub 配置一致）
- `REPO_PATH`: 仓库路径（可选，默认：/home/ubuntu/ai-doc）
- `DEPLOY_SCRIPT`: 部署脚本路径（可选，默认：/home/ubuntu/ai-doc/deploy.sh）

### 2. GitHub Webhook 配置

1. 在 GitHub 仓库中，进入 Settings → Webhooks → Add webhook
2. 设置 Payload URL 为 `http://your-server-ip:9000/webhook`
3. 设置 Content type 为 `application/json`
4. 设置 Secret 为与 `.env` 文件中 `WEBHOOK_SECRET` 相同的值
5. 选择事件类型为 `Create`（仅监听标签创建事件）
6. 保存配置

## 使用方法

### 1. 安装依赖

```bash
# 使用 uv（推荐）
uv sync

# 或仅安装依赖（使用启动脚本）
./start.sh --install
```

### 2. 启动服务

#### 开发环境

```bash
# 使用 Python 直接启动
python main.py

# 或使用启动脚本（默认开发环境）
./start.sh
```

#### 生产环境

```bash
# 使用 Gunicorn（推荐）
./start.sh -e production

# 自定义配置
./start.sh -e production -p 8000 -w 8
```

#### 启动脚本选项

```bash
./start.sh [选项]

选项：
    -e, --environment ENV    环境类型 (development/production)，默认: development
    -h, --host HOST          监听主机，默认: 0.0.0.0
    -p, --port PORT          监听端口，默认: 9000
    -w, --workers NUM        Gunicorn 工作进程数，默认: 4
    --install                仅安装/更新依赖
    --help                   显示帮助信息
```

### 3. 触发部署

在 main 分支上创建标签即可触发自动部署：

```bash
git tag v1.0.0
git push origin v1.0.0
```

## 功能说明

- 仅处理在 **main 分支**上创建的标签
- 自动拉取最新代码
- 执行部署脚本
- 非 main 分支的标签会被自动忽略