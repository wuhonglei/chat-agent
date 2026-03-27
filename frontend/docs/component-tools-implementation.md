# 组件工具实现说明（当前实现）

> 状态：现网实现。
> 本文档基于 `src/componentTools/*`、`src/interfaces/*`、`src/services/chat.ts` 当前代码整理。

## 1. 目标

前端支持将 AI 回复中的特定代码块渲染为业务组件，并把组件触发规则随聊天请求发送给后端，由后端决定是否返回组件数据。

## 2. 前端注册结构

组件在 `src/componentTools/index.ts` 中注册，每项包含：

- `name`：组件工具名（示例：`weather`）
- `component`：React 组件
- `typeSourceFile`：用于生成 schema 的类型文件路径
- `whenCondition`：`and | or`
- `when`：
  - `mcp_tool_names`
  - `mcp_tool_call_content`
  - `user_message`

对应类型定义在 `src/interfaces/componentTools.ts`：

- `ComponentToolItem`
- `ComponentToolRequestItem`

## 3. 请求协议（前端 -> 后端）

聊天请求类型在 `src/interfaces/chat.ts`：

- `ChatRequest.componentToolsForBackend: Pick<ComponentToolRequestItem, "name" | "whenCondition" | "when">[]`

这意味着前端传递的是“组件名称 + 触发条件”，而不是完整 schema 内容。

## 4. 接口调用

前端流式聊天接口：

- `POST /api/chat/stream`

调用位置：

- `src/services/chat.ts`（`chatAPI.streamMessage`）

请求体经 snake_case 转换后发送到后端，后端字段对应 `component_tools_for_backend`。

## 5. 渲染约定

前端按代码块语言标识识别组件渲染（例如 `component_<name>` 模式），匹配到已注册组件后进行 JSON 解析与渲染；解析失败则降级为普通代码块展示。

## 6. Schema 生成与产物

当前文档口径：schema 由前端构建流程自动生成并放在静态目录，后端按组件名拉取与缓存。
更详细说明见：

- `frontend/docs/schema-generation.md`
- `backend/docs/COMPONENT_TOOLS_PRD.md`

## 7. 维护注意事项

- 新增组件时，必须同步更新 `src/componentTools/index.ts`；
- `name` 需要与后端可识别的组件工具名保持一致；
- `when` 触发条件字段应与后端 `ComponentToolWhen` 语义一致；
- 文档中不再使用旧字段名 `component_tools` / `component_tool_names` 作为现网口径。
