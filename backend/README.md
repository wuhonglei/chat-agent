# AI Doc Q&A System - Backend

企业级知识库问答系统后端服务，基于 RAG (Retrieval-Augmented Generation) 技术，使用 DeepSeek API 提供智能文档问答功能。

## 功能特性

- **智能问答**：基于 RAG 技术的精准问答
- **向量检索**：使用 ChromaDB 进行高效向量存储和检索
- **内部系统集成**：支持 Confluence 等企业内部系统知识库检索
- **联网搜索**：支持联网搜索，通过 [tavily](https://www.tavily.com/) 获取最新信息
- **混合搜索**：结合向量检索和 BM25 关键词搜索，提高检索准确性
- **重排序**：使用 Sentence Transformers 对检索结果进行重排序
- **缓存机制**：Redis 缓存提升响应速度

## 技术栈

- **框架**: FastAPI
- **LLM**: DeepSeek API
- **向量数据库**: ChromaDB
- **缓存**: Redis
- **语言**: Python 3.10+

## 项目结构

```
backend/
├── app/
│   ├── api/           # API 路由和端点
│   ├── core/          # 核心配置和依赖
│   ├── models/        # 数据模型
│   ├── services/      # 业务逻辑服务
│   ├── utils/         # 工具函数
│   └── main.py        # 应用入口
├── config/            # 配置文件
├── data/             # 数据存储目录
│   ├── vectordb/     # 向量数据库存储
│   └── temp/         # 临时文件
├── tests/            # 测试文件
├── .env.example      # 环境变量示例
├── Dockerfile        # Docker 配置
├── pyproject.toml    # 项目依赖配置
└── uv.lock          # 依赖锁文件
```

## 快速开始

### 环境要求

- Python 3.10+
- Redis (可选，用于缓存)
- ChromaDB (自动安装)

### 安装步骤

1. **克隆项目**
```bash
git clone <repository-url>
cd ai-doc/backend
```

2. **安装 uv 包管理器**（推荐）
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

3. **创建虚拟环境并安装依赖**
```bash
uv venv
source .venv/bin/activate  # Linux/Mac
# 或
.venv\Scripts\activate  # Windows

uv pip sync
```

4. **配置环境变量**
```bash
cp .env.example .env
# 编辑 .env 文件，填入你的配置信息
```

5. **启动服务**
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

访问 http://localhost:8000/docs 查看 API 文档

6. **数据库迁移**

> **提示**：使用 Docker Compose 部署时，数据库迁移会在容器启动时自动执行，无需手动操作。

6.1 **生成迁移文件**
```bash
uv run alembic revision --autogenerate -m "Add conversation table"
```

6.2 **查看当前应用的版本**
```bash
uv run alembic current
```

output is as below, `6fc87d2a678f` means the current version of the application.
```txt
(ai-doc-backend) ➜  backend git:(main) uv run alembic current
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
6fc87d2a678f
```

6.3 **查看迁移历史**
```bash
uv run alembic history
```

output is as below, `6fc87d2a678f` means the current version of the application. `01fb8247599b` means the next version of the application.
```txt
(ai-doc-backend) ➜  backend git:(main) ✗ uv run alembic history
6fc87d2a678f -> 01fb8247599b (head), conversations 表增加 last_message_updated_at 字段
<base> -> 6fc87d2a678f, chore: 初始化数据库迁移
```

6.4 **执行迁移（本地开发环境）**
```bash
uv run alembic upgrade head
```

6.5 **Docker 环境中的迁移**

使用 Docker Compose 时，迁移会自动执行。如需手动执行：

```bash
# 进入容器执行迁移
docker-compose exec backend uv run alembic upgrade head

# 或使用 docker exec
docker exec -it ai-doc-backend uv run alembic upgrade head
```

## API 接口

### 问答接口

- `POST /api/v1/chat/ask` - 提问
- `GET /api/v1/chat/history` - 获取对话历史

### 知识库管理

- `POST /api/v1/knowledge/sync` - 同步外部文档源
- `GET /api/v1/knowledge/status` - 获取知识库状态

## 配置说明

### DeepSeek API 配置

在 `.env` 文件中配置：

```env
LLM_API_KEY=your_api_key
LLM_MODEL=deepseek-chat
DEEPSEEK_EMBEDDING_MODEL=deepseek-embed
```

### 向量数据库配置

```env
CHROMA_PERSIST_DIRECTORY=./data/vectordb
CHROMA_COLLECTION_NAME=documents
```



## Docker 部署

### 使用 Docker Compose（推荐）

项目已配置 Docker Compose，支持自动数据库迁移。在项目根目录执行：

```bash
# 启动所有服务（数据库迁移会自动执行）
docker-compose up -d

# 查看日志
docker-compose logs -f backend
```

**自动迁移功能**：
- 容器启动时会自动等待数据库就绪
- 自动执行 `alembic upgrade head` 应用所有迁移
- 迁移完成后自动启动应用服务

### 单独构建和运行

1. **构建镜像**
```bash
docker build -t ai-doc-backend .
```

2. **运行容器**
```bash
docker run -d \
  --name ai-doc-backend \
  -p 8000:8000 \
  -v $(pwd)/data:/app/data \
  --env-file .env \
  ai-doc-backend
```

**注意**：使用 `start.sh` 启动脚本时，容器会自动执行数据库迁移，无需手动运行 `alembic upgrade head`。

## 开发指南

### 安装开发依赖

```bash
uv pip install -e ".[dev]"
```

### 代码格式化

```bash
black app/
ruff check app/ --fix
```

### 类型检查

项目已配置严格的类型检查，可以在开发过程中及早发现参数不匹配等错误。

#### 安装依赖
```bash
# 安装生产依赖（不包含 mypy）
uv sync

# 安装开发依赖（包含 mypy）
uv sync --extra dev
```

#### 运行类型检查
```bash
# 使用 make 命令
make check

# 或直接使用 mypy
uv run mypy app/

# 检查特定文件
uv run mypy app/agents/context_compression_agent.py
```

详见 [类型检查指南](docs/type_checking_guide.md)。

## 性能优化

- **向量索引**: ChromaDB 自动建立 HNSW 索引，提供快速相似度搜索
- **缓存策略**: Redis 缓存热门问题答案，减少 LLM 调用
- **异步处理**: 使用 FastAPI 异步特性处理并发请求
- **文档分块**: 智能分块策略，平衡检索精度和效率

## 安全考虑

- API 密钥使用环境变量管理
- 预留 JWT 认证接口

## 常见问题

### Q: 如何添加新的文档格式支持？
A: 在 `app/services/document_processor.py` 中添加新的解析器

### Q: 如何调整检索精度？
A: 修改 `.env` 中的 `SEARCH_TOP_K`、`MIN_RELEVANCE_SCORE` 参数

### Q: 如何集成其他 LLM？
A: 在 `app/services/llm_service.py` 中实现新的 LLM 适配器

## 许可证

MIT License

## 贡献指南

欢迎提交 Issue 和 Pull Request！

## 联系方式

如有问题，请提交 Issue 或联系维护团队。