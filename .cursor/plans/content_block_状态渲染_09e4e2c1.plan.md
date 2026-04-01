---
name: content block 状态渲染
overview: 将 `ContentBlocksRender` 改为按 `ContentBlock[]` 原始顺序渲染，并引入统一的数字枚举作为前端展示态；避免把所有流式瞬时状态都固化到后端 block 协议中，只在必要处补充终态信号。
todos:
  - id: derive-render-status
    content: 设计统一数字枚举，并实现基于 `contentBlocks` 的前端状态推导函数
    status: completed
  - id: render-in-order
    content: 将 `ContentBlocksRender` 改为按 `ContentBlock[]` 顺序逐块渲染
    status: completed
  - id: adapt-thinking-text
    content: 改造 `ReasoningBlockRender` 和 `TextBlockRender` 以消费 block 自身推导状态
    status: completed
  - id: tooluse-result-merge
    content: 抽出轻量 `ToolUseBlockRender`，并把 `ToolUseBlock` 与 `ToolResultBlock` 按 `toolCallId/toolUseId` 归并展示
    status: completed
  - id: backend-signal-if-needed
    content: 仅在前端推导不足时，再补最小后端终态信号
    status: completed
isProject: false
---

# ContentBlocks 顺序渲染与状态收敛

## 设计结论

- 建议**统一状态枚举**，但把它定义为**前端渲染态**，而不是所有 block 的后端持久化字段。
- 原因：`开始`、`流式中`、`调用中` 这类状态本质上依赖 SSE 事件上下文，落到 `content_blocks` 快照里会造成协议臃肿，而且历史消息只需要最终事实数据，不需要保留每一帧瞬时态。
- 建议保留后端事实字段：`type`、`text`、`toolCallId`、`argumentsText`、`isError`、`toolUseId`；前端基于 `append/delta/tool_delta/finalize_round/done` 和 block 顺序/关联关系推导状态。
- 若现有 `ReasoningBlockRender` 必须明确区分“已结束”，优先通过“后续 block 出现 / 消息 done / 工具轮 finalize”推导终态；只有当这三类信号仍不足以满足交互时，再补一个**轻量终态信号**，不要把全部 1/2/3/4/5/6 状态都回传给后端。

## 目标改动

- 把 [frontend/src/pages/ChatPage/components/ChatMessage/components/ContentBlocksRender/index.tsx](/Users/apple/Desktop/code/chat-agent/frontend/src/pages/ChatPage/components/ChatMessage/components/ContentBlocksRender/index.tsx) 从“聚合 thinking/text 后统一渲染”改成“按 `contentBlocks` 顺序逐块渲染”。
- 复用并改造 [frontend/src/pages/ChatPage/components/ChatMessage/components/ContentBlocksRender/ReasoningBlockRender.tsx](/Users/apple/Desktop/code/chat-agent/frontend/src/pages/ChatPage/components/ChatMessage/components/ContentBlocksRender/ReasoningBlockRender.tsx) 和 [frontend/src/pages/ChatPage/components/ChatMessage/components/ContentBlocksRender/TextBlockRender.tsx](/Users/apple/Desktop/code/chat-agent/frontend/src/pages/ChatPage/components/ChatMessage/components/ContentBlocksRender/TextBlockRender.tsx)。
- 新增一个 content-block 级别的**状态推导层**，把 `ThinkingBlock` / `ToolUseBlock` / `TextBlock` 映射成统一数字枚举。
- `ToolResultBlock` 继续不单独展示，而是通过 `toolCallId` / `toolUseId` 挂到对应 `ToolUseBlock` 上形成单条工具调用 UI。

## 推荐状态模型

- 在 [frontend/src/interfaces/contentBlock.ts](/Users/apple/Desktop/code/chat-agent/frontend/src/interfaces/contentBlock.ts) 附近新增统一枚举，例如 `ContentBlockRenderStatus`。
- 建议使用单一数字空间，但只让不同 block 消费自己需要的子集：
  - `1 Start`
  - `2 Streaming`
  - `3 StreamFinished`
  - `4 Running`
  - `5 Success`
  - `6 Error`
  - `100 Done`
- 各 block 的映射建议：
  - `ThinkingBlock`: `1/2/100`
  - `TextBlock`: `1/2/3`
  - `ToolUseBlock`: `1/2/3/4/5/6`
  - `ToolResultBlock`: 不暴露独立状态，只作为 `ToolUseBlock` 的结果数据源
- 这样既满足“统一枚举值”的诉求，也避免为了形式统一给 `ToolResultBlock` 塞一个无实际消费价值的 `status`。

## 实现路径

1. 在前端新增 block 视图模型/推导函数
  - 新增一个纯函数模块，输入 `contentBlocks`、当前消息是否 `isStreaming`，输出按顺序可渲染的列表。
  - 其中完成：
    - 识别每个 block 的前后文位置
    - 用 `toolCallId` / `toolUseId` 关联 `ToolUseBlock` 与 `ToolResultBlock`
    - 为 `ThinkingBlock` / `TextBlock` / `ToolUseBlock` 推导统一枚举状态
2. 重写 `ContentBlocksRender` 的渲染入口
  - 遍历原数组顺序，不再使用 `getMessageThinkingFromBlocks` / `getMessageTextFromBlocks` 聚合展示。
  - `tool_result` 不直接产出 DOM；遇到 `tool_use` 时从已索引结果中取对应结果一起渲染。
3. 改造 `ReasoningBlockRender`
  - 让它改为接收 `status` 或 `isDoing` 这类由推导层计算出的值，移除外部 `isReasoning` 的会话级强绑定。
  - 折叠/展开逻辑改为依据 block 自身状态，而不是全局“当前正在 reasoning”。
4. 抽出轻量工具调用渲染组件
  - 参考 [frontend/src/pages/ChatPage/components/ChatMessage/components/ToolCallBlock/index.tsx](/Users/apple/Desktop/code/chat-agent/frontend/src/pages/ChatPage/components/ChatMessage/components/ToolCallBlock/index.tsx) 的现有样式与状态文案，但方案上明确**不直接复用旧时间线容器**。
  - 新增独立的 `ToolUseBlockRender`，仅接收单个 `tool_use` 的名称、参数文本、推导状态、关联结果/错误等最小渲染数据，避免引入旧的 `toolCalls` timeline 类型、hooks 与会话级状态依赖。
  - `ContentBlocksRender` 或其推导层负责把 `tool_result` 归并成 `ToolUseBlockRender` 所需 props；旧 `ToolCallBlock` 只保留可复用的纯展示片段，不能把整套时间线状态机搬进来。
5. 只在必要时补后端信号
  - 若前端推导后，`ThinkingBlock` 的终态仍无法稳定驱动 UI，再在 [backend/app/agents/utils/content_blocks.py](/Users/apple/Desktop/code/chat-agent/backend/app/agents/utils/content_blocks.py) / [backend/app/schemas/chat.py](/Users/apple/Desktop/code/chat-agent/backend/app/schemas/chat.py) 增加一个最小信号，例如仅补“thinking 已结束”的事件或字段。
  - 不建议第一步就给全部 block 增加持久化 `status` 字段。

## ToolUseBlockRender 约束

- 建议把 `ToolUseBlockRender` 设计成纯展示组件，props 只保留最小集合，例如：
  - `name?: string`
  - `argumentsText: string`
  - `status: ContentBlockRenderStatus`
  - `result?: { content: string; summary?: string; isError: boolean }`
  - `defaultExpanded?: boolean`
- 不把 `ToolCallMessage`、`TimelineMessage`、`eventType`、`useTimelineMessages()`、`useEmitterWithCondition()` 带入新组件。
- 旧 `ToolCallItemContent.tsx` 中“参数高亮 / 成功结果展示 / 错误文案”这类纯展示逻辑可复用或下沉，但必须改成消费上面的最小 props，而不是消费旧消息模型。
- 折叠策略以 block 自身状态为准：
  - `Start/Streaming/Running` 默认展开
  - `Success/Error/Done` 默认折叠，但允许用户手动展开查看参数与结果

## 工具块状态映射细化

- `tool_use` 初次 append 且 `argumentsText` 为空或刚开始拼装时：`Start`
- `tool_delta` 持续追加参数时：`Streaming`
- 收到 `finalize_round` 且该工具尚未关联 `tool_result`：`Running`
- 关联到 `tool_result.isError === false`：`Success`
- 关联到 `tool_result.isError === true`：`Error`
- 对历史消息回放：
  - 有 `tool_result` 时直接落 `Success/Error`
  - 无 `tool_result` 但消息已结束时，保守落 `Done` 或继续维持 `Running`，实现时需在计划落地阶段统一选一种，不回退到旧时间线事件判断

## 主要文件

- [frontend/src/interfaces/contentBlock.ts](/Users/apple/Desktop/code/chat-agent/frontend/src/interfaces/contentBlock.ts)
- [frontend/src/pages/ChatPage/components/ChatMessage/components/ContentBlocksRender/index.tsx](/Users/apple/Desktop/code/chat-agent/frontend/src/pages/ChatPage/components/ChatMessage/components/ContentBlocksRender/index.tsx)
- [frontend/src/pages/ChatPage/components/ChatMessage/components/ContentBlocksRender/ReasoningBlockRender.tsx](/Users/apple/Desktop/code/chat-agent/frontend/src/pages/ChatPage/components/ChatMessage/components/ContentBlocksRender/ReasoningBlockRender.tsx)
- [frontend/src/pages/ChatPage/components/ChatMessage/components/ContentBlocksRender/TextBlockRender.tsx](/Users/apple/Desktop/code/chat-agent/frontend/src/pages/ChatPage/components/ChatMessage/components/ContentBlocksRender/TextBlockRender.tsx)
- [frontend/src/pages/ChatPage/components/ChatMessage/components/ContentBlocksRender/ToolUseBlockRender.tsx](/Users/apple/Desktop/code/chat-agent/frontend/src/pages/ChatPage/components/ChatMessage/components/ContentBlocksRender/ToolUseBlockRender.tsx)
- [frontend/src/pages/ChatPage/components/ChatMessage/components/ToolCallBlock/ToolCallItemContent.tsx](/Users/apple/Desktop/code/chat-agent/frontend/src/pages/ChatPage/components/ChatMessage/components/ToolCallBlock/ToolCallItemContent.tsx)
- [frontend/src/pages/ChatPage/components/ChatMessage/components/AssistantMessage.tsx](/Users/apple/Desktop/code/chat-agent/frontend/src/pages/ChatPage/components/ChatMessage/components/AssistantMessage.tsx)
- 备选后端最小补充点： [backend/app/agents/utils/content_blocks.py](/Users/apple/Desktop/code/chat-agent/backend/app/agents/utils/content_blocks.py) 、 [backend/app/schemas/chat.py](/Users/apple/Desktop/code/chat-agent/backend/app/schemas/chat.py)

## 验证重点

- `thinking -> tool_use -> tool_result -> thinking -> text` 能按原数组顺序稳定展示。
- `tool_result` 乱序到达时，仍能通过 `toolCallId` / `toolUseId` 正确归并到对应 `tool_use`。
- 流式过程中：
  - thinking 可从展开中自动切换到完成态
  - tool_use 可经历参数流式拼装、调用中、成功/失败
  - text 可经历开始、流式中、结束
- 历史消息回显不依赖全局 `isReasoning` / `isCallingMcpTools` 也能得到正确展示态。
