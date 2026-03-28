# Webhook for GitHub

## 概述

这是一个基于 GitHub Webhook 的部署脚本，用于自动部署代码到服务器。当在 main 分支上创建标签时，会自动触发部署流程。

## 配置

### 1. 环境变量配置

复制 `.env.example` 为 `.env` 并填入实际值：

```bash
cp .env.example .env
```

编辑 `.env` 文件，设置以下环境变量：

- `WEBHOOK_SECRET`: GitHub Webhook 的 Secret（**必需**，与 GitHub 配置一致，未设置时启动脚本会报错并退出）
- `REPO_PATH`: 仓库路径（可选，默认：/home/ubuntu/chat-agent）
- `DEPLOY_SCRIPT`: 部署脚本路径（可选，默认：/home/ubuntu/chat-agent/deploy.sh）
- `DEBUG`: 调试模式（可选，默认：False）

启动脚本会从当前目录的 `.env` 文件自动加载环境变量。

### 2. GitHub Webhook 配置

1. 在 GitHub 仓库中，进入 Settings → Webhooks → Add webhook
2. 设置 Payload URL 为 `http://your-server-ip:9000/webhook`
3. 设置 Content type 为 `application/json`
4. 设置 Secret 为与 `.env` 文件中 `WEBHOOK_SECRET` 相同的值
5. 选择事件类型为 `Create`（仅监听标签创建事件）
6. 保存配置

## 使用方法

### 1. 启动服务（推荐使用 start.sh）

`start.sh` 会依次执行：加载 `.env` → 检查 `WEBHOOK_SECRET` → 激活虚拟环境（`.venv` 或 `venv`）→ 检查并安装依赖（优先使用 `uv sync`，否则 `pip install -e .`）→ 使用 **Gunicorn** 启动 Flask 应用。

```bash
# 直接启动（默认 host=0.0.0.0, port=9000, workers=1）
./start.sh

# 自定义端口
./start.sh -p 8000

# 自定义主机和端口
./start.sh -h 127.0.0.1 -p 8000

# 多进程
./start.sh -w 4
```

### 2. 仅安装依赖

```bash
# 使用启动脚本（会优先用 uv，否则用 pip）
./start.sh --install
```

也可手动安装：

```bash
uv sync
# 或
pip install -e .
```

### 3. 启动脚本选项

```bash
./start.sh [选项]

选项：
    -h, --host HOST          监听主机，默认: 0.0.0.0
    -p, --port PORT          监听端口，默认: 9000
    -w, --workers NUM        Gunicorn 工作进程数，默认: 1
    --install                仅安装/更新依赖后退出
    --help                   显示帮助信息
```

Gunicorn 使用 `main:app`、worker 类型为 `sync`、日志级别为 `info`，访问日志与错误日志输出到标准输出。

### 4. 触发部署

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
