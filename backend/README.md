# AI Doc Q&A System - Backend

企业级知识库问答系统后端服务，基于 RAG (Retrieval-Augmented Generation) 技术，使用 DeepSeek API 提供智能文档问答功能。

## 功能特性

- **文档管理**：支持 PDF、Word、Markdown、纯文本等多种格式文档上传和解析
- **智能问答**：基于 RAG 技术的精准文档问答
- **向量检索**：使用 ChromaDB 进行高效向量存储和检索
- **内部系统集成**：支持 Confluence、Google Workspace 等企业内部系统知识库检索
- **联网搜索**：支持联网搜索，通过 [tavily](https://www.tavily.com/) 获取最新信息
- **文件搜索**: 支持对用户上传的文件(全部文件或指定文件)进行检索
- **混合搜索**：结合向量检索和 BM25 关键词搜索，提高检索准确性
- **重排序**：使用 Sentence Transformers 对检索结果进行重排序
- **缓存机制**：Redis 缓存提升响应速度

## 技术栈

- **框架**: FastAPI
- **LLM**: DeepSeek API
- **向量数据库**: ChromaDB
- **文档处理**: LangChain, Unstructured
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
│   ├── documents/    # 上传的文档
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

**生成迁移文件**
```bash
uv run alembic revision --autogenerate -m "Add conversation table"
```

**执行迁移**
```bash
uv run alembic upgrade head
```

## API 接口

### 文档管理

- `POST /api/v1/documents/upload` - 上传文档
- `GET /api/v1/documents` - 获取文档列表
- `DELETE /api/v1/documents/{doc_id}` - 删除文档

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

### 文档处理配置

```env
CHUNK_SIZE=1000          # 文档分块大小
CHUNK_OVERLAP=200        # 分块重叠字符数
MAX_FILE_SIZE_MB=50      # 最大文件大小
```

## Docker 部署

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

```bash
mypy app/
```

### 运行测试

```bash
pytest
pytest --cov=app tests/  # 带覆盖率
```

## 性能优化

- **向量索引**: ChromaDB 自动建立 HNSW 索引，提供快速相似度搜索
- **缓存策略**: Redis 缓存热门问题答案，减少 LLM 调用
- **异步处理**: 使用 FastAPI 异步特性处理并发请求
- **文档分块**: 智能分块策略，平衡检索精度和效率

## 安全考虑

- API 密钥使用环境变量管理
- 文件上传大小限制
- 文件类型白名单验证
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