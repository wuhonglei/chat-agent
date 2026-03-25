---
name: multimodal-chat-backend
overview: 在不改动消息表列结构的前提下，让用户消息支持文本+图片+文件：上传得到 FileObject；客户端将 ContentPart 数组写入 ChatRequest.content；后端将其序列化入库到 MessageDb.content（JSON 字符串），并在检索/摘要/工具与 LLM 组包时分别做“文本提取”和“多模态 content 映射”，提供 conversation 级 artifacts 访问能力。
todos:
  - id: audit-route-prefix
    content: 统一上传返回的 `artifact_url` 路径前缀与实际路由为 `/api/conversation`，确保 image_url 可被 LLM 正确访问
    status: pending
  - id: harden-upload
    content: 补齐上传大小限制、MIME/扩展名白名单、错误处理与日志；确保 artifacts 路径校验覆盖边界
    status: pending
  - id: history-truncate-mm
    content: 检查并修正 history 截断/token 统计对 JSON content 的处理，必要时统一用 extract_text_from_content() 计数
    status: pending
  - id: optional-file-inject
    content: （可选）文件 markdown 内容注入到 LLM 的策略：读取 md、截断、注入 text part，并加 token 上限
    status: pending
isProject: false
---

## 目标与约束

- **目标**：在现有“消息表重设计”基础上，实现对话中 **图片+文件+文本** 的统一表达、入库、回放、以及喂给 LLM。
- **约束**：
  - **不新增 DB 列/表**：继续复用 `MessageDb.content`（字符串 or JSON parts 的序列化字符串）。
  - **存储**：使用本地文件系统（`data/conversations/{conversation_id}/user-data/uploads`）。
  - **图片给模型**：使用 `image_url`（OpenAI-compatible 格式），URL 指向后端 artifacts 接口。

## 已有设计与代码现状（对齐点）

- **ContentParts 数据模型已存在**：`ContentPart = text | image | file`，并用 `FileObject` 描述上传文件元数据，见 `[backend/app/schemas/content.py](backend/app/schemas/content.py)`。
- **content 的解析/序列化/文本提取已存在**：`parse_content_parts()` / `serialize_message_content()` / `extract_text_from_content()` / `content_parts_to_openai_content()`，见 `[backend/app/utils/content.py](backend/app/utils/content.py)`。
- **ChatRequest 已支持多模态入参**：`content: str | list[ContentPart]`，见 `[backend/app/schemas/chat.py](backend/app/schemas/chat.py)`。
- **用户消息入库已支持多模态**：`MessageDbService.create_user_message(... content: str | list[ContentPart])` 会序列化写入 DB，见 `[backend/app/services/message/message_db.py](backend/app/services/message/message_db.py)`。
- **LLM 组包已做多模态分支**：`format_chat_message_for_llm()` 会在 `content` 为“JSON 字符串”时转为 OpenAI 多模态列表（包含 `image_url`），见 `[backend/app/utils/message.py](backend/app/utils/message.py)`。
- **上传与 artifacts 接口已实现**：
  - `POST /{conversation_id}/uploads`：保存到会话 uploads 目录；PDF 走 `MarkItDown()` 转 `.md` 并回填 `markdown_`* 字段。
  - `GET /{conversation_id}/artifacts/{artifact_path:path}`：仅允许访问 `/mnt/user-data/uploads/`*。
  见 `[backend/app/api/conversation.py](backend/app/api/conversation.py)`。

## 需要补齐/加固的关键链路

### 1) LLM 可访问性与 URL 形态

- `content_parts_to_openai_content()` 当前对 image part 输出 `{"type":"image_url","image_url":{"url": <artifact_url>}}`。
- 需要确认 **LLM 服务端是否能访问这个 URL**：
  - 若 LLM 在同一内网/容器环境：确保 `artifact_url` 是可达的绝对 URL（或由网关补全）。
  - 若只能访问公网：需要在网关层或后端生成可访问的完整地址。
- 计划动作：将 `artifact_url` 的路由前缀统一为 `/api/conversation`，并确保与后端实际挂载的路由前缀一致。

### 2) 安全与限制（必须做的最小集）

- **上传大小限制**：在 FastAPI 层/反向代理层增加 max upload size。
- **MIME/扩展名白名单**：图片（png/jpg/webp/gif）、文档（pdf、txt、md、docx 等按需），拒绝可执行文件。
- **路径穿越防护**：artifacts 已限制 prefix + 禁止 `/` 和 `\\`，保留并补齐边界用例。
- **鉴权**：上传与 artifacts 都依赖 `require_auth`，保持一致；如未来要分享链接，再做签名 URL。

### 3) “文件 part”参与推理的策略

- 图片：用 `image_url` 直接喂给模型。
- 文件：
  - PDF 已转 Markdown：在 `extract_text_from_content()` 中优先拼 `markdown_artifact_url`，可以继续沿用。
  - 进一步增强（可选）：在发送给 LLM 时，把 markdown 内容（文本）作为额外 text part 注入（需要后端在 artifacts 读取 md 内容并截断/限额）。

### 4) 历史截断与 token 统计

- 当前 `ChatService.stream_message()`、`MCPToolsAgent.stream_execute()` 都通过 `extract_text_from_content(chat_request.content)` 把多模态归一成可检索/可压缩的文本，这一点正确。
- 计划动作：检查 `[backend/app/utils/history_truncate.py](backend/app/utils/history_truncate.py)` 是否对 `ChatMessageItem.content` 的“JSON 字符串”情况做了正确 token 计算与截断（若没有，需要按 `extract_text_from_content()` 结果计数）。

## 里程碑与验收（后端视角）

- **Phase1（可用）**：上传图片/PDF/文件 → 能生成 `FileObject`（含 artifacts URL）→ Chat 入库成功（`MessageDb.content` 可存 JSON parts）→ LLM 组包时 `image_url` 出现在最终 messages payload 中。
- **Phase2（可靠）**：补齐 URL 可达性、上传限制/白名单、history truncate/token 统计对多模态无回归。
- **Phase3（体验，可选）**：文件 markdown 内容注入到 LLM（读取、截断、限额、失败降级）。
