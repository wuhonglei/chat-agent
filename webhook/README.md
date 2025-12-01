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

1. 安装依赖：
   ```bash
   uv sync
   ```

2. 启动服务：
   ```bash
   python main.py
   ```
   或使用提供的启动脚本：
   ```bash
   bash start.sh
   ```

3. 在 main 分支上创建标签即可触发自动部署：
   ```bash
   git tag v1.0.0
   git push origin v1.0.0
   ```

## 功能说明

- 仅处理在 **main 分支**上创建的标签
- 自动拉取最新代码
- 执行部署脚本
- 非 main 分支的标签会被自动忽略