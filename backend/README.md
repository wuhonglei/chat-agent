# AI Doc Backend

后端服务基于 FastAPI，负责认证、会话管理、流式聊天、MCP 工具编排与数据持久化。

## 当前能力

- 聊天流式接口：`POST /api/chat/stream`
- 会话管理：创建 / 列表 / 详情 / 更新 / 删除
- 用户认证：短信登录、微信登录、JWT 鉴权
- MCP 工具：Context7、天气、联网搜索、代码执行、时间、IP 定位
- 用户能力：用户信息、用户记忆、头像上传

## 技术栈

- Python 3.10+
- FastAPI + Uvicorn
- SQLModel + Alembic
- PostgreSQL（pgvector）
- fastmcp
- OpenAI 兼容模型调用

## 目录结构（当前）

```text
backend/
├── app/
│   ├── api/                    # 路由层
│   ├── agents/                 # Agent 编排
│   ├── core/                   # 配置、DB、JWT
│   ├── mcp/                    # MCP 管理与服务器
│   ├── middleware/             # 中间件
│   ├── models/                 # SQLModel 模型
│   ├── schemas/                # Pydantic 模型
│   ├── services/               # 业务服务层
│   ├── prompts/
│   └── main.py
├── alembic/
├── docs/
├── tests/
├── Makefile
├── Dockerfile
├── pyproject.toml
└── uv.lock
```

## 本地开发

### 1) 安装依赖

```bash
uv sync --extra dev --group dev
```

### 2) 配置环境变量

```bash
cp .env.example .env
```

> 可选：若使用 Nacos，按 `.env` 配置连接信息；若本地直连数据库，建议设置 `DATABASE__HOST=localhost`。

### 3) 启动开发服务

```bash
make dev
```

服务地址：`http://localhost:8000`
OpenAPI：`http://localhost:8000/docs`

## 数据库迁移

```bash
# 执行迁移
make migrate

# 查看当前版本
uv run alembic current

# 查看历史
uv run alembic history
```

> 提示：首次空库场景下，可先让应用建表后再 `alembic stamp head`，具体见根目录 `AGENTS.md`。

## 常用命令

```bash
make help
make dev
make start
make lint
make check
make test
```

## API 路由（当前实现）

- 认证：`/api/auth/*`
- 聊天：`/api/chat/*`
- 会话：`/api/conversation/*`
- 消息：`/api/message/*`
- 用户：`/api/user/*`
- 文件：`/api/file/*`
- 健康：`/api/health/*`

## Docker 运行

通常从项目根目录使用 `docker compose` 启动（同时拉起 postgres / backend / frontend）。

```bash
docker compose up -d --build
```
