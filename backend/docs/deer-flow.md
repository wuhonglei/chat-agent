# DeerFlow 多模态处理与记忆系统问答整理

## 1. 后端多模态消息处理

**问：** 后端是如何处理多模态消息的（图片/文件）？

**答：** DeerFlow 后端通过分层架构处理多模态消息，包括文件上传、中间件注入和工具处理三个核心环节。

### 支持的多模态形式

**问：** 支持哪些多模态形式？

**答：** DeerFlow 支持图片、文档和普通文本文件：

- **图片文件：** jpg、jpeg、png、webp 格式，通过 `view_image_tool` 读取并转换为 base64 格式注入 LLM 上下文（参考 `view_image_tool.py` 第 60–64 行）
- **文档文件：** PDF、PowerPoint、Excel、Word 格式，自动转换为 Markdown 格式（参考 `FILE_UPLOAD.md` 第 87–95 行）
- **普通文件：** 任何文本文件，通过 `read_file` 工具直接读取

### 文件大小限制处理

**问：** 文件大小超出限制会如何处理？

**答：** 文件大小超出限制时会在多个层面拦截：

- **飞书渠道：** 图片 10MB、文件 30MB 限制，超出则记录警告并跳过（参考 `feishu.py` 第 205–211 行）
- **Telegram 渠道：** 文件 50MB 限制
- **前端验证：** 显示错误信息，阻止上传
- **系统级限制：** 100MB，通过 nginx 配置（参考 `FILE_UPLOAD.md` 第 207 行）

### 图片压缩处理

**问：** 对于图片，是否进行了压缩处理？

**答：** 不会，DeerFlow 不对图片进行压缩处理：

- `view_image_tool` 直接读取图片文件并转换为 base64 格式（参考 `view_image_tool.py` 第 78–86 行）
- 通过文件大小限制而非压缩来控制资源使用
- 保持图片原始质量确保视觉模型分析效果

### PDF 文本截断处理

**问：** 如果 PDF 文本内容过长，内容截断是如何处理的？

**答：** 通过多种机制进行截断：

- **工具级别：** `read_file_tool` 支持 `start_line` 和 `end_line` 参数进行行范围读取
- **记忆更新：** 单条消息超过 1000 字符时截断（参考 `prompt.py` 第 337–339 行）
- **记忆注入：** 根据 token 限制进行智能截断（参考 `prompt.py` 第 291–298 行）

### 文件存储机制

**问：** 文件在数据库存储时，存储在什么字段？

**答：** DeerFlow 不使用传统数据库，采用文件系统存储：

- **实际存储：** 线程隔离目录 `backend/.deer-flow/threads/{thread_id}/user-data/uploads/`（参考 `FILE_UPLOAD.md` 第 193–203 行）
- **元数据字段：** `filename`、`size`、`path`、`virtual_path`、`artifact_url` 等（参考 `uploads.py` 第 92–98 行）
- **完整接口：** 包含 markdown 相关字段用于文档转换

### HTTP 请求文件字段

**问：** HTTP 请求中，文件存储在什么字段？

**答：** 文件存储在 `files` 字段中：

- **请求格式：** `multipart/form-data`，文件存储在 `files` 字段（参考 `API.md` 第 391–401 行）
- **后端接收：** 通过 `files: list[UploadFile] = File(...)` 参数接收（参考 `uploads.py` 第 40–44 行）
- **前端发送：** 使用 `formData.append("files", file)` 添加文件

### 消息发送请求格式

**问：** 上传完文件，用户输入文本内容，回车后，发送的请求格式是什么？

**答：** 通过 LangGraph API 发送多模态消息：

`POST /api/langgraph/threads/{thread_id}/runs`

```json
{
  "input": {
    "messages": [
      {
        "type": "human",
        "content": [{ "type": "text", "text": "用户输入" }],
        "additional_kwargs": {
          "files": [
            {
              "filename": "doc.pdf",
              "size": 1234567,
              "path": "/mnt/user-data/uploads/doc.pdf"
            }
          ]
        }
      }
    ]
  },
  "config": { "recursion_limit": 1000 },
  "context": { "thinking_enabled": true, "thread_id": "thread_id" }
}
```

（参考 `hooks.ts` 第 347–388 行）

### 核心设计特点

#### 数据流分离

- **文件上传：** 先上传获取元数据，消息提交时只包含路径信息
- **多模态内容：** 支持文本和文件附件的组合
- **流式响应：** 通过 LangGraph 流式 API 获取实时响应

#### 处理策略差异

| 类型     | 说明                                       |
| -------- | ------------------------------------------ |
| **图片** | 自动注入 base64 数据供 LLM 直接分析      |
| **文档** | 只提供路径信息，需要 Agent 主动读取       |
| **文本** | 通过工具按需读取，支持行范围控制         |

这种设计确保了系统的高效性、灵活性和上下文连续性。

---

## 2. PDF 文件内容处理

**问：** 底层调用 LLM API 时，PDF 文件内容是否会以 text 文本形式拼接到用户提示词中？

**答：** PDF 文件内容不会自动拼接到用户提示词中。系统只提供文件路径信息，Agent 需要主动使用工具读取文件内容。

---

## 3. 图片 base64 内容处理

**问：** 底层调用 LLM API 时，图片 base64 内容是否会以 text 文本形式拼接到用户提示词中？

**答：** 图片 base64 内容会拼接到用户提示词中，但不是以纯文本形式，而是以多模态消息格式注入。

---

## 4. view_image_tool 调用机制

**问：** `view_image_tool` 是模型主动调用的，还是代码层面主动调用的？

**答：** `view_image_tool` 是模型（LLM）主动调用的，不是代码层面主动调用的。

---

## 5. 工具调用结果保留

**问：** `view_image_tool` 调用后，图片的 base64 以 human message 形式插入的 messages 中，那么该工具的调用结果是否会保留并在下次 LLM 调用时传入？

**答：** `view_image_tool` 的调用结果会保留并在后续 LLM 调用时传入，但通过特定的机制管理。

---

## 6. 图片数据重复问题

**问：** `view_image_tool` 工具的 ToolMessage 作为对话历史的一部分永久保留在 messages 中，另外 `view_image_tool` 返回的图片 base64 会作为 human message 插入到 messages 中，这是否会造成图片消息重复？

**答：** 不会造成图片消息重复。两个消息的作用和内容完全不同。

---

## 7. PDF 文件读取结果

**问：** 那么对于 PDF 文件的读取，工具结果是怎样的？

**答：** PDF 文件读取的工具结果是文件的文本内容，不是 base64 或其他格式。

---

## 8. PDF 文件消息存在形式

**问：** 那是否意味着 PDF 文件的读取结果只存在于 ToolMessage，不会存在于 HumanMessage？

**答：** 是的，PDF 文件的读取结果只存在于 ToolMessage 中，不会存在于 HumanMessage 中。

---

## 9. 历史文件处理

**问：** 如果在第一轮对话中上传了图片和 PDF，该轮回答结束。当用户发起新一轮对话时，历史的图片和 PDF 是如何处理的？

**答：** 在新一轮对话中，历史图片和 PDF 的处理方式不同：图片数据会保留并可供 LLM 继续访问，而 PDF 只保留文件路径信息需要重新读取。

---

## 10. 工具调用列表传递

**问：** 那是否意味着新一轮对话发起时，历史消息中的工具调用列表不会传递到 LLM API 调用请求中？

**答：** 不，历史消息中的工具调用列表会传递到 LLM API 调用请求中。

---

## 11. 工具调用信息保留

**问：** 历史对话的工具调用信息是否会被保留？

**答：** 是的，历史对话的工具调用信息会被保留。

---

## 12. 短期对话概念

**问：** 什么是短期对话？

**答：** 短期对话是指当前活跃会话中的完整消息上下文，包含所有对话历史和工具调用信息（参考 `memory_middleware.py` 第 20–42 行）。

---

## 13. Conversation 与短期对话

**问：** 一个 conversation 内的所有对话是否是短期对话？

**答：** 是的，一个 conversation 内的所有对话都属于短期对话。

---

## 14. 长期记忆存储流程

**问：** 长期记忆的存储流程？

**答：** DeerFlow 的长期记忆存储流程是一个多阶段的异步处理系统，通过中间件、队列和 LLM 分析实现智能记忆更新（参考 `memory_middleware.py` 第 108–149 行）。

---

## 15. 记忆更新数据范围

**问：** 记忆更新时，会将整个 thread 的历史对话都传过去吗？

**答：** 不会，记忆更新时只会传递过滤后的部分对话内容，而不是整个 thread 的历史对话（参考 `prompt.py` 第 303–346 行）。

---

## 16. 第一轮消息传递

**问：** 如果当前 thread 有 2 轮问答，那么第一轮的 human message 是否会传给长期记忆更新？

**答：** 是的，第一轮的 human message 会传给长期记忆更新，但需要满足特定条件（参考 `memory_middleware.py` 第 108–149 行）。

---

## 核心机制总结

### 多模态处理差异

| 类型 | 说明 |
|------|------|
| **图片** | 通过 `view_image_tool` 读取，base64 数据自动注入到 HumanMessage 中供 LLM 直接分析 |
| **PDF** | 通过 `read_file` 读取，内容只存在于 ToolMessage 中，需要 Agent 主动处理 |

### 数据持久化策略

- **短期对话：** 保留完整的消息历史，包括所有工具调用信息
- **长期记忆：** 只保留过滤后的用户输入和 AI 响应摘要

### 工具调用机制

- **模型驱动：** LLM 自主决定何时调用工具
- **状态管理：** 通过状态字段和中间件协调数据流
- **防重复机制：** 确保数据不会重复注入

这种设计确保了系统的高效性、灵活性和上下文连续性。

---

## 延伸阅读（DeepWiki）

- [Harness vs App Layer (bytedance/deer-flow)](https://deepwiki.com/bytedance/deer-flow/3.2-harness-vs-app-layer)
- [Chat Interface and Thread Management (bytedance/deer-flow)](https://deepwiki.com/bytedance/deer-flow/4.2-chat-interface-and-thread-management)
- [Memory System (bytedance/deer-flow)](https://deepwiki.com/bytedance/deer-flow/5.8-memory-system)
