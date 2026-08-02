# Chat Agent Backend - Agent Guide

## 项目概述

Chat Agent 后端是 AI 对话平台的服务端，基于 FastAPI，提供流式对话、多轮会话、MCP 工具与用户认证等能力；并支持基于 RAG 的检索与问答。

### 核心功能

- **智能问答**：基于 RAG 技术的精准问答，支持流式响应
- **MCP 工具集成**：通过 Model Context Protocol 集成多种外部工具（搜索、天气、文件、Shell、代码执行、Skill 管理、时间、Context7 等）
- **Agent 架构**：`ChatSessionAgent` 在同一 messages 线程上编排 MCP 工具多轮与流式应答；`TitleGenerationAgent` 负责标题生成
- **对话管理**：支持多轮对话、对话历史管理、消息持久化、上下文压缩
- **用户认证**：基于 JWT 的用户认证体系
- **虚拟文件系统 / 沙箱**：会话级 workspace、uploads、outputs（见 `app/vfs/`）；代码与 Shell 执行走 `app/sandbox/`

## 技术栈

- **框架**：FastAPI + Uvicorn
- **语言**：Python 3.10+
- **数据库**：PostgreSQL + SQLModel + Alembic（迁移）
- **缓存**：Redis（会话/状态等）+ 本地缓存
- **LLM**：DeepSeek API / OpenAI 兼容 API
- **MCP**：fastmcp（Model Context Protocol 实现）
- **向量检索能力**：PostgreSQL（pgvector）/ FAISS（按具体模块使用）
- **对象存储**：腾讯云 COS
- **可观测性**：Langfuse、Prometheus
- **配置中心**：Nacos

## 项目结构

```
backend/
├── app/
│   ├── api/              # API 路由和端点
│   │   ├── auth.py           # 认证相关接口
│   │   ├── chat.py           # 对话流式接口（核心）
│   │   ├── conversation.py   # 对话管理接口
│   │   ├── message.py        # 消息管理接口
│   │   ├── user.py           # 用户管理接口
│   │   ├── user_data.py      # 用户数据 / 工作区接口
│   │   ├── file.py           # 文件上传接口
│   │   ├── avatars.py        # 头像接口
│   │   ├── code.py           # 代码相关接口
│   │   ├── models.py         # 模型列表接口
│   │   ├── health.py         # 健康检查接口
│   │   └── deps.py           # 路由级依赖（如 MCP manager）
│   ├── agents/           # Agent 实现
│   │   ├── base.py                   # Agent 基类
│   │   ├── chat_session_agent.py     # 单会话编排（工具多轮 + 流式应答）
│   │   ├── chat_session_state.py     # 会话轮次状态机
│   │   ├── title_generation_agent.py # 标题生成 Agent
│   │   ├── tool_executor.py          # 工具执行编排
│   │   ├── mcp_tool_execution.py     # MCP 工具会话执行
│   │   ├── tool_call_*.py            # 工具调用策略 / 护栏 / 流式解析
│   │   └── utils/                    # 响应生成、内容块、结果后处理等
│   ├── agent_skills/     # Skill 注册与类型
│   ├── core/             # 核心配置与基础设施
│   │   ├── config.py     # 应用配置（Pydantic Settings）
│   │   ├── db.py         # 数据库连接
│   │   ├── jwt.py        # JWT 管理
│   │   ├── redis.py      # Redis 连接
│   │   ├── cache.py      # 缓存与会话状态失效
│   │   ├── observability.py  # Langfuse 等可观测性
│   │   └── nacos/        # Nacos 配置中心
│   ├── mcp/              # MCP 相关
│   │   ├── client.py         # MCPClientManager
│   │   ├── gateway.py        # MCP 网关
│   │   ├── registry.py       # Server / 工具注册
│   │   ├── connection_pool.py
│   │   ├── reload.py         # 配置热更新回调
│   │   └── mcp_servers/      # 各 MCP Server 实现
│   │       ├── tavily_mcp/           # 联网搜索
│   │       ├── weather_mcp/          # 天气查询
│   │       ├── file_mcp/             # 文件读写（VFS）
│   │       ├── shell_mcp/            # Shell 执行
│   │       ├── code_exec_mcp/        # 代码执行沙箱
│   │       ├── skill_manager_mcp/    # Skill 管理
│   │       ├── time_mcp/             # 时间服务
│   │       └── context7_mcp/         # Context7 文档
│   ├── vfs/              # 虚拟路径映射（workspace / uploads / outputs / skills）
│   ├── sandbox/          # 本地 / Docker 执行后端
│   ├── protocols/        # SSE / 聊天协议事件构建
│   ├── middleware/       # 中间件
│   │   ├── logging.py
│   │   └── exception_handler.py
│   ├── models/           # 数据库模型（SQLModel）
│   │   ├── user.py
│   │   ├── conversation_db.py
│   │   ├── message_db.py
│   │   ├── conversation_contexts_db.py
│   │   └── kb_file_chunk_embedding_db.py
│   ├── schemas/          # Pydantic 模型
│   │   ├── chat.py
│   │   ├── config.py
│   │   ├── conversation.py
│   │   ├── llm.py
│   │   └── ...
│   ├── services/         # 业务逻辑服务（按领域分包）
│   │   ├── chat/                 # 对话编排、历史上下文、KB RAG、后处理
│   │   ├── chat_upload/          # 会话附件上传与衍生
│   │   ├── conversation/         # 会话服务
│   │   ├── message/              # 消息服务
│   │   ├── user/                 # 用户与记忆服务
│   │   ├── auth/                 # 认证服务
│   │   └── base_service/         # LLM、模型解析等基础设施
│   ├── utils/            # 工具函数（日志、认证依赖、上下文压缩、token 等）
│   ├── prompts/          # 提示词模板
│   └── main.py           # 应用入口
├── alembic/              # 数据库迁移
│   ├── env.py
│   └── versions/
├── skills/               # 内置 / 公共 Skills（挂载为 /mnt/skills/public/）
├── tests/
├── data/                 # 运行时数据
│   └── user_data/        # 用户会话工作区、上传与产出（见 app/vfs/paths.py）
├── docs/
├── scripts/              # 运维 / 辅助脚本
├── init-db/              # 数据库初始化相关
├── pyproject.toml
├── uv.lock
├── alembic.ini
├── Dockerfile
├── start.sh              # 启动脚本（含自动迁移）
└── Makefile
```

## 开发环境搭建

### 1. 安装依赖

使用 `uv` 作为包管理器（推荐）：

```bash
# 安装 uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# 创建虚拟环境并安装依赖
uv venv
source .venv/bin/activate  # Linux/Mac
# 或 .venv\Scripts\activate  # Windows

# 安装生产依赖
uv sync

# 安装开发依赖
uv sync --extra dev --group dev
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 文件，填入 Nacos 连接信息或其他配置
```

配置优先级（从高到低）：
1. 初始化参数
2. 环境变量
3. Nacos 配置中心

### 3. 启动服务

```bash
# 开发模式（热重载）
make dev
# 或
APP__DEBUG=1 uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 生产模式
make start
# 或
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

访问 http://localhost:8000/docs 查看 API 文档。

## 数据库迁移

使用 Alembic 管理数据库迁移：

```bash
# 生成迁移文件
uv run alembic revision --autogenerate -m "描述"

# 查看当前版本
uv run alembic current

# 查看迁移历史
uv run alembic history

# 执行迁移
uv run alembic upgrade head

# 回滚迁移
uv run alembic downgrade -1
```

**注意**：Docker 部署时会自动执行迁移（通过 `start.sh` 脚本）。

## 代码风格与质量

### 格式化与检查

```bash
# 格式化代码（使用 ruff）
make format
# 或
uv run format.py

# 快速格式化
make format-ruff

# 代码检查
make lint

# 类型检查（使用 mypy）
make check
```

### 代码规范

- **格式化**：使用 Ruff 进行代码格式化和检查
- **类型检查**：使用 mypy，配置在 `mypy.ini`，启用严格模式
- **行长度**：不强制限制（E501 忽略），但建议保持合理
- **引号**：使用双引号
- **缩进**：4 个空格

### 类型检查例外

以下模块在 `mypy.ini` 中被忽略类型检查错误：
- `tests.*`

## 测试

```bash
# 运行所有测试
make test
# 或
uv run pytest

# 运行特定测试
uv run pytest tests/test_specific.py -v
```

测试配置在 `pyproject.toml`：
```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
```

## 架构设计

### Agent 执行流程

对话请求的处理流程（由 `ChatOrchestrator` / `ChatService` 驱动）：

1. **ChatSessionAgent**：在同一 messages 线程上循环——按需调用 MCP 工具、聚合 `content_blocks`、流式生成最终回复
2. **TitleGenerationAgent**：（可选，常与主流程并行）生成对话标题
3. **后处理**：消息落库、会话状态刷新、记忆 / 缓存失效等（`PostProcessService` 等）

工具侧细节（策略、护栏、批处理、结果后处理）落在 `app/agents/tool_*`、`mcp_tool_execution.py` 与 `agents/utils/`。

### MCP 架构

- **MCPClientManager**（`app/mcp/client.py`）：统一管理多个 MCP Server 连接
- **registry / gateway / connection_pool**：注册、路由与连接池
- 支持多种传输方式：FastMCPTransport（本地）、StreamableHttpTransport（HTTP）、StdioTransport（子进程）
- 配置变更可通过 `reload.py` 热更新
- 健康检查和可用性检测

### 配置管理

使用 Pydantic Settings 分层管理配置：

```python
class Settings(BaseSettings):
    app: AppConfig                    # 应用基础配置
    models: ModelsConfig              # 模型配置（providers + scenarios 两层）
    embedding_model: EmbeddingModelConfig    # Embedding 模型 API 配置
    mcp: MCPConfig                    # MCP 配置
    storage: StorageConfig            # 存储配置
    security: SecurityConfig          # 安全配置（JWT）
    database: DatabaseConfig          # 数据库配置
    # ...
```

模型解析：通过 `app/services/base_service/model_resolver.py` 的 `resolve_model_ref("provider/model")` /
`resolve_scenario("text_generation"|"title_generation"|"summarization")` 将配置解析为运行时 `LLMConfig`
（含 `context_limit`，供 `TokenCalculator`）。

## API 设计规范

### 响应格式

统一使用 `ApiResponse` 包装：

```python
{
    "code": 0,        # 0 表示成功，非 0 表示错误
    "msg": "success", # 消息
    "data": {}        # 数据
}
```

### 流式响应

对话接口使用 SSE (Server-Sent Events) 格式：

```
event: ack
data: {"id": "...", "role": "user", ...}

event: tool_start
data: {"tool_name": "..."}

event: delta
data: {"content": "..."}

event: done
data: {"content_length": 100, ...}
```

### 认证

使用 JWT Token，通过 `Authorization: Bearer <token>` 头部传递。

依赖注入方式：
```python
from app.utils.auth_deps import require_auth

@router.post("/endpoint")
async def endpoint(_auth: None = Depends(require_auth)):
    ...
```

## 日志规范

使用 `loguru` 进行结构化日志记录：

```python
from app.utils.logger import logger

# 普通日志
logger.info("Message", key1=value1, key2=value2)

# 错误日志（自动包含堆栈）
logger.error("Error occurred", error=e, exc_info=True)

# 异常捕获
logger.exception("Unhandled exception", error=e)
```

日志特点：
- 结构化输出（JSON 格式）
- 自动包含时间戳、日志级别
- 支持额外的上下文字段

## 安全考虑

1. **API 密钥**：通过环境变量或 Nacos 配置中心管理，不硬编码
2. **JWT 认证**：使用 RSA 密钥对，私钥签名、公钥验证
3. **代码执行沙箱**：使用 RestrictedPython 实现安全的代码执行环境
4. **SQL 注入防护**：使用 SQLModel/SQLAlchemy ORM，参数化查询
5. **CORS**：生产环境需要配置允许的域名

## Docker 部署

```bash
# 构建镜像
docker build -t chat-agent-backend .

# 运行容器
docker run -d \
  --name chat-agent-backend \
  -p 8000:8000 \
  -v $(pwd)/data:/app/data \
  --env-file .env \
  chat-agent-backend
```

**启动流程**：
1. 等待数据库连接可用（最多 60 秒）
2. 执行数据库迁移 `alembic upgrade head`
3. 启动 Gunicorn（workers = CPU 核心数 * 2）

## 常用命令速查

| 命令 | 说明 |
|------|------|
| `make install` | 安装依赖 |
| `make dev` | 开发模式启动 |
| `make start` | 生产模式启动 |
| `make format` | 格式化代码 |
| `make lint` | 代码检查 |
| `make check` | 类型检查 |
| `make test` | 运行测试 |
| `make clean` | 清理临时文件 |

## 开发注意事项

1. **数据库模型变更**：修改 `app/models/` 后，需要生成并执行 Alembic 迁移
2. **新增 API**：在 `app/api/` 创建路由文件，在 `app/main.py` 注册
3. **新增 MCP Server**：在 `app/mcp/mcp_servers/` 创建，并在 `app/mcp/registry.py` / 相关配置中注册
4. **配置变更**：在 `app/schemas/config.py` 定义模型，在 `app/core/config.py` 使用
5. **Agent 开发**：继承 `BaseAgent`；主对话能力优先扩展 `ChatSessionAgent`（及 `tool_*` / `agents/utils/`）；流式入口优先语义化命名（例如 `stream_session_events`），统一抽象仍遵循 `stream_execute` 约定
6. **VFS / 沙箱路径**：用户数据布局与虚拟路径约定见 `app/vfs/paths.py` 与 `docs/VFS_AND_SANDBOX.md`

## 调试技巧

1. **开启调试模式**：设置 `APP__DEBUG=1`，日志会更详细
2. **查看 MCP 工具列表**：访问健康检查接口或查看启动日志
3. **数据库调试**：使用 `alembic current` 和 `alembic history` 查看迁移状态
4. **API 测试**：使用 `/docs` 端点的 Swagger UI 进行交互式测试
