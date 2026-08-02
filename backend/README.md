# Chat Agent Backend

后端服务基于 FastAPI，负责认证、会话管理、流式聊天、MCP 工具编排与数据持久化。

## 当前能力

- 聊天流式接口：`POST /api/chat/stream`
- 聊天续流接口：`POST /api/chat/stream/resume`
- 聊天模型列表：`GET /api/chat/models`
- 会话管理：创建 / 列表 / 详情 / 更新 / 删除
- 用户认证：短信登录、微信登录、JWT 鉴权
- MCP 工具：Context7、天气、联网搜索、代码执行、时间
- 用户能力：用户信息、用户记忆、头像上传

## 技术栈

- Python 3.10+
- FastAPI + Uvicorn
- SQLModel + Alembic
- PostgreSQL（pgvector）
- Redis（SSE 续传缓冲 + turn 幂等）
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
>
> Nacos gRPC 相关环境变量（可选）：`NACOS_GRPC_TIMEOUT_MS`（默认 5000）、`NACOS_GRPC_PORT_OFFSET`（默认 1000）、`NACOS_GRPC_KEEPALIVE_MS`（默认 180000，过短易触发 `too_many_pings`）。生产启动见 `start.sh`：**不要**对 Gunicorn 使用 `--preload`（与 Nacos gRPC 不兼容）。

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
- 聊天：`/api/chat/stream`、`/api/chat/stream/resume`、`/api/chat/models`
- 会话：`/api/conversation/*`
- 消息：`/api/message/delete/{message_id}`、`/api/message/feedback/{message_id}`
- 用户：`/api/user/*`
- 文件：`/api/file/*`
- 健康：`/api/health/*`
- 代码执行：`/api/code/*`

## 聊天附件链路（近期高频）

### 1) 上传与预览接口

- 上传附件：`POST /api/file/upload`（需要登录）
- 预览附件：`GET /api/file/preview/{user_id}/{storage_key}`（无需登录；依赖 `storage_key` 不可猜测）

上传成功后返回 `AttachmentBlock`：
- 图片返回 `ImageBlock`
- PDF / Excel / Word / PowerPoint 分别返回 `PdfBlock` / `ExcelBlock` / `DocxBlock` / `PptxBlock`，并在 `markdown` 中携带同源 Markdown 预览信息
- Markdown（`.md` / `.markdown` / `text/markdown`）返回独立 `MarkdownBlock`
- 纯文本 / 代码文件返回 `TextFileBlock`

预览 URL 统一为：`/api/file/preview/{user_id}/{storage_key}`。当前 `storage_key` 使用会话级 v4 布局：

```text
{conversation_id}/{display_name}
{conversation_id}/derived/{stem}.md
```

真实落盘位置位于 `data/user_data/{user_id}/conversations/{conversation_id}/uploads/`，其中 `derived/` 保存 PDF / Excel 转出的 Markdown。

### 2) 文件类型与限制

- 单文件大小上限：`10MB`
- 图片：`JPEG / PNG / GIF / WebP`
- PDF：`application/pdf`
- Excel：`.xlsx`
- Word：`.docx`
- PowerPoint：`.pptx`
- Markdown：`.md` / `.markdown` / `text/markdown`，内容必须是 UTF-8 文本
- 纯文本 / 代码文件：支持 `.csv`、`.tsv`、`.txt`、`.log`、`.py`、`.js`、`.ts`、`.tsx`、`.vue`、`.sql`、`.go` 等扩展名，内容必须是 UTF-8
- 图片会在服务端按最长边 `2048px` 等比缩放（超限时），并重新编码后落盘
- PDF 校验文件头 `%PDF-`；xlsx/docx/pptx 校验 OOXML 魔数 `PK\x03\x04`，再执行 MinerU -> Markdown 转换

### 3) 文档 -> Markdown 转换策略

`MinerUMarkdownConverter` 通过 MinerU SaaS（`mineru.net`）批量解析接口统一转换 PDF、Excel、Word、PowerPoint：

1. 申请预签名上传 URL
2. PUT 上传本地文件
3. 轮询任务状态
4. 下载结果 ZIP，写入 `derived/{stem}.md`，图片合并到 `derived/images/`

关键配置位于 `settings.mineru`（Nacos `mineru` 对象）：
- `enabled`
- `api_url`
- `api_key`
- `model_version`
- `poll_interval_seconds`
- `poll_timeout_seconds`

### 4) 附件安全约束

- 真实落盘文件名使用 UUID，避免用户可控路径
- `preview` 允许会话根文件（含 pdf/xlsx/docx/pptx）、`derived/*.md` 与 `derived/images/*`（jpg/jpeg/png/gif/webp）
- `user_id` 与路径边界会做校验，非法请求统一返回 404
- 展示名仅用于 UI，服务端会做安全清洗（去路径、非法字符、长度限制）

### 5) 附件 token_size 与按需 RAG（agent_mode=0）

上传阶段：

- 文档转 Markdown / 文本落盘后，计算并写入 `token_size`（派生 md 写在 `markdown.token_size`）
- **不再**在上传时做分块 embedding

问答阶段（仅 `agent_mode=0`，且只看**当前轮** `content_blocks`）：

- `token_size <= short_doc_max_tokens`：直接注入完整 md/文本
- `token_size > short_doc_max_tokens`：若 DB 尚无向量则按需分块 embedding，再对该附件做 Top-K 检索
- 历史消息中的附件不参与本轮 RAG；`agent_mode>0` 改为注入 `attachment_uploads` 清单，由文件工具按需读取

### 6) 常见排障

- `agent_mode=0`：后端从当前轮附件（若有）或历史用户消息附件收集 `content_id`，通过 `KbRagContextService` 构建 `<attachment_context>`。
- `agent_mode>0`：后端跳过附件 RAG，改为在用户提示词中注入 `<attachment_uploads>` 清单，包含 `name`、`type`、`virtual_path`、`size`、`uploaded_this_turn`。PDF / Excel 还会附带派生 Markdown 的 `virtual_path`，模型可用 file MCP 按需读取 `/mnt/user-data/uploads/...`。

### 6) 常见排障

- `400 仅支持 ...` / `不支持的文本文件类型`：文件类型不在允许列表
- `400 ...不能超过 10MB`：超出大小限制
- `400 PDF/Word/PowerPoint 文件无效或已损坏`：文件头校验失败
- `502 MinerU 转换失败`：检查 Nacos `mineru.api_key`、外部服务可用性和轮询超时配置

---

## 代码执行 API（/api/code/execute）

### 接口说明

- 路径：`POST /api/code/execute`
- 请求体：
  - `code: string`
  - `language: "python" | "javascript" | "typescript"`
- 响应：`ApiResponse[CodeExecResponse]`

服务端通过 Piston 沙箱执行代码，基础地址来自：

- `settings.mcp.mcp_servers["code-exec-mcp"].env["piston_base_url"]`

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
id: 1
data: {"type":"<event_type>","data":{...}}
```

`id` 由 Redis 版 `StreamRelay` 分配（1-based），客户端通过请求头 `Last-Event-ID` 续传。续流请求示例：

```http
POST /api/chat/stream/resume
Last-Event-ID: 12

{"assistant_message_id":"assistant-message-id"}
```

客户端通过 `Last-Event-ID` 请求头传递最近消费的 `seq`。

当前事件类型：

- `ack`：用户/助手消息占位已创建
- `refresh_conversation`：会话元信息更新
- `title`：会话标题生成完成
- `content_block`：内容块流式增量（`append` / `delta` / `tool_delta` / `finalize_round` / `done`）
- `done`：本轮结束（包含内容长度、推理长度、工具调用次数、更新时间）
- `error`：本轮失败

续流缓冲与 `client_turn_id` 幂等缓存均存储在 Redis，可跨 worker 共享；依赖 Redis TTL（活跃默认 2h，close 后默认 30min）。多 worker 部署需保证 Redis 可达。`stop` 通过 Redis meta `status=stopped` 跨 worker 生效（同 worker 仍有本地 task cancel 快路径）。

## 模型列表与图片输入约束

前端模型选择来自 `GET /api/chat/models`，该接口返回 `text_generation` 场景（`default_model` + `alternatives`）的脱敏模型信息：

- `model_id`：模型引用 `provider/model_name`（如 `dashscope/kimi-k2.6`），聊天请求中的 `model_id` 使用该值
- `title` / `description`：前端展示文案
- `image_support`：是否支持图片输入（由模型 `capabilities` 是否含 `image` 推导）

模型配置采用 `models.providers`（按供应商聚合）+ `models.scenarios`（场景选模）两层结构，必须包含 `text_generation` / `title_generation` / `summarization` 场景。聊天请求 `model_id` 为空或无法解析时回退 `text_generation` 的默认模型；当请求携带图片块且所选模型 `image_support=false` 时，`POST /api/chat/stream` 会返回 `400 当前模型不支持图片输入`。

## Docker 运行

通常从项目根目录使用 `docker compose` 启动（同时拉起 postgres / backend / frontend）。

```bash
docker compose up -d --build
```
