# Chat Agent Backend

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

## 聊天附件链路（近期高频）

### 1) 上传与预览接口

- 上传附件：`POST /api/file/upload`（需要登录）
- 预览附件：`GET /api/file/preview/{user_id}/{filename}`（无需登录）

上传成功后返回 `ApiResponse[AttachmentBlock]`，其中 `data` 按类型分为：

- 图片：`ImageBlock`
- PDF：`PdfBlock`，并在 `markdown` 字段中携带同源 `MarkdownBlock`

预览 URL 统一为：`/api/file/preview/{user_id}/{filename}`。

### 2) 文件类型与限制

- 单文件大小上限：`10MB`
- 图片：`JPEG / PNG / GIF / WebP`
- PDF：`application/pdf`
- 图片会在服务端按最长边 `2048px` 等比缩放（超限时），并重新编码后落盘
- PDF 会先校验文件头（`%PDF-`），再执行 PDF -> Markdown 转换

### 3) 落盘与返回字段

附件保存到 `backend/data/user_data/{user_id}/uploads/`：

- 图片文件名为 `{uuid}.{ext}`；`id` 使用同一个 UUID。
- PDF 文件名为 `{sha256}.pdf`，Markdown 文件名为 `{sha256}.md`；`id` 使用内容 SHA-256。
- `url` 指向站内预览路径，`name` 是清洗后的展示名，`size` 是实际落盘字节数。
- `mime` 会按服务端识别结果归一化，例如 `image/jpg` 返回为 `image/jpeg`。

### 4) PDF -> Markdown 与向量入库

`save_chat_pdf` 在上传阶段同步完成转换与索引，任一环节失败会让上传请求失败：

1. 按内容 SHA-256 去重；同用户相同 PDF 且 `.pdf`/`.md` 均存在时复用文件并跳过向量入库。
2. `PdfMarkdownConverter` 读取前 `detect_pages` 页文本长度：
   - 大于等于 `scan_text_threshold`：视为文本型 PDF，使用 `MarkItDown` 转换。
   - 小于阈值：视为扫描型 PDF，调用 `PP-StructureV3` 转换。
3. 转换后的 Markdown 写入同目录 `.md` 文件。
4. Markdown 经 `MarkdownTextSplitter` 分块，调用当前 embedding 模型生成向量，写入 `kb_file_chunk_embeddings`。

关键配置位于 `settings.pdf_markdown`：

- `scan_text_threshold`
- `detect_pages`
- `pp_structure_api_url`
- `pp_structure_token`
- `poll_timeout_seconds`

分块与检索相关配置位于 `settings.kb_file_rag`：

- `chunk_size`
- `chunk_overlap`
- `retrieval_top_k`
- `relevance_score_threshold`

### 5) 附件安全约束

- 真实落盘文件名不使用用户原始文件名：图片使用 UUID，PDF/Markdown 使用内容 SHA-256。
- `preview` 仅允许单段文件名和白名单后缀：`jpg/jpeg/png/gif/webp/pdf/md`。
- `user_id` 与路径边界会做校验；公开预览接口中的非法请求统一返回 `404`，避免泄露路径信息。
- 展示名仅用于 UI，服务端会做安全清洗（去路径、控制字符、Windows 非法字符并限制长度）。

### 6) 常见排障

- `400 仅支持 ...`：`Content-Type` 不在允许列表，或 PDF 未使用 `application/pdf`
- `400 ...不能超过 10MB`：单文件超过后端读取上限
- `400 图片文件无效或已损坏`：Pillow 无法识别图片内容
- `400 PDF 文件无效或已损坏`：文件头校验失败
- `502 PDF 转 Markdown 失败`：检查 `PDF_MARKDOWN__PP_STRUCTURE_TOKEN`、`PDF_MARKDOWN__PP_STRUCTURE_API_URL` 与外部服务超时
- `502 PDF 分块向量入库失败`：检查 embedding 模型配置、数据库 pgvector 扩展和 `kb_file_chunk_embeddings` 表结构

---

## 代码执行 API（/api/code/execute）

### 接口说明

- 路径：`POST /api/code/execute`
- 请求体：
  - `code: string`
  - `language: "python" | "javascript" | "typescript"`
- 响应：`ApiResponse[CodeExecResponse]`

服务端通过 Piston 沙箱执行代码，基础地址来自：

- `settings.mcp.code_exec_mcp.piston_base_url`

### 请求示例

```bash
curl -X POST "http://localhost:8000/api/code/execute" \
  -H "Content-Type: application/json" \
  -d '{
    "language": "python",
    "code": "print(1 + 2)"
  }'
```

### 响应字段（核心）

- `run.stdout` / `run.stderr` / `run.output`
- `run.code` / `run.signal`
- `compile.*`（仅编译型语言在有编译阶段时返回）

### 使用与排障建议

- 若输出为空，先确认代码中有显式输出（如 `print` / `console.log`）
- 编译或运行错误优先看 `stderr`
- 若全部请求失败，优先检查 Piston 地址连通性与配置注入

---

## 聊天流式事件约定（/api/chat/stream）

SSE 数据格式统一为：

```text
data: {"type":"<event_type>","data":{...}}
```

当前事件类型：

- `ack`：用户/助手消息占位已创建
- `refresh_conversation`：会话元信息更新
- `title`：会话标题生成完成
- `content_block`：内容块流式增量（`append` / `delta` / `tool_delta` / `finalize_round` / `done`）
- `done`：本轮结束（包含内容长度、推理长度、工具调用次数、更新时间）
- `error`：本轮失败

## Docker 运行

通常从项目根目录使用 `docker compose` 启动（同时拉起 postgres / backend / frontend）。

```bash
docker compose up -d --build
```
