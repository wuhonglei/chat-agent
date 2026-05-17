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
- 预览附件：`GET /api/file/preview/{user_id}/{filename}`（无需登录）

上传成功后返回 `AttachmentBlock`：
- 图片返回 `ImageBlock`
- PDF 返回 `PdfBlock`，并在 `markdownBlock` 中携带同源 Markdown 预览信息

预览 URL 统一为：`/api/file/preview/{user_id}/{filename}`。

### 2) 文件类型与限制

- 单文件大小上限：`10MB`
- 图片：`JPEG / PNG / GIF / WebP`
- PDF：`application/pdf`
- 图片会在服务端按最长边 `2048px` 等比缩放（超限时），并重新编码后落盘
- PDF 会先校验文件头（`%PDF-`），再执行 PDF -> Markdown 转换

### 3) PDF -> Markdown 转换策略

`PdfMarkdownConverter` 按 PDF 类型分流：

1. 文本型 PDF：`MarkItDown` 直接转换
2. 扫描型 PDF：调用 `PP-StructureV3` 服务转换

关键配置位于 `settings.pdf_markdown`：
- `scan_text_threshold`
- `detect_pages`
- `pp_structure_api_url`
- `pp_structure_token`
- `poll_timeout_seconds`

### 4) 附件安全约束

- 真实落盘文件名使用 UUID，避免用户可控路径
- `preview` 仅允许匹配 `uuid + 扩展名` 的文件名（支持 jpg/jpeg/png/gif/webp/pdf/md）
- `user_id` 与路径边界会做校验，非法请求统一返回 404
- 展示名仅用于 UI，服务端会做安全清洗（去路径、非法字符、长度限制）

### 5) 常见排障

- `400 仅支持 ...`：文件类型不在允许列表
- `400 ...不能超过 10MB`：超出大小限制
- `400 PDF 文件无效或已损坏`：文件头校验失败
- `502 PDF 转 Markdown 失败`：检查 `PDF_MARKDOWN__PP_STRUCTURE_TOKEN`、外部服务可用性和超时配置

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
data: {"type":"<event_type>","data":{...},"seq":1}
```

`seq` 由服务端内存中的 `StreamRelay` 注入，用于 `POST /api/chat/stream/resume` 断线续流。续流请求体为：

```json
{
  "assistant_message_id": "assistant-message-id",
  "last_seq": 12
}
```

当前事件类型：

- `ack`：用户/助手消息占位已创建
- `refresh_conversation`：会话元信息更新
- `title`：会话标题生成完成
- `content_block`：内容块流式增量（`append` / `delta` / `tool_delta` / `finalize_round` / `done`）
- `done`：本轮结束（包含内容长度、推理长度、工具调用次数、更新时间）
- `error`：本轮失败

续流缓冲仅在当前进程和活动流生命周期内有效；生成完成或进程重启后，续流接口会返回空 SSE。

## 模型列表与图片输入约束

前端模型选择来自 `GET /api/chat/models`，该接口从 `settings.model_map` 返回经过脱敏的模型信息：

- `model_id`：`model_map` 配置键，聊天请求中的 `model_id` 使用该值
- `title` / `description`：前端展示文案
- `image_support`：是否支持图片输入

`model_map` 必须包含 `default`。当聊天请求携带图片块且所选模型 `image_support=false` 时，`POST /api/chat/stream` 会返回 `400 当前模型不支持图片输入`。

## Docker 运行

通常从项目根目录使用 `docker compose` 启动（同时拉起 postgres / backend / frontend）。

```bash
docker compose up -d --build
```
