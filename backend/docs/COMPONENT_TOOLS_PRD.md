# 组件工具接入说明（当前实现）

> 状态：现网实现。本文档描述 `component_tools_for_backend` 在后端的实际处理链路。

## 1. 输入协议

前端通过 `POST /api/chat/stream` 传入 `ChatRequest`，其中组件工具相关字段为：

- `component_tools_for_backend: list[ComponentToolConfig]`
- 每个配置包含：
  - `name`：组件工具名（如 `weather`）
  - `when_condition`：`and | or`
  - `when`：触发条件（`mcp_tool_names`、`mcp_tool_call_content`、`user_message`）

对应模型位置：

- `app/schemas/chat.py`：`ChatRequest`、`ComponentToolConfig`、`ComponentToolWhen`

## 2. Schema 获取与缓存

后端使用 `ComponentSchemaService` 获取组件 JSON Schema：

- 代码位置：`app/services/component/component_schema_service.py`
- 默认地址：`settings.component_schema_api_url`（通常为 `/component-schemas/` 静态目录）
- 获取方式：
  - `get_schema(name)`：单个获取（含缓存）
  - `get_schemas(names)`：批量获取
- 缓存策略：
  - 类级 `_schema_cache`（进程内缓存）
  - 非 debug 模式优先命中缓存

## 3. 执行链路（Agent 模式）

当前 `ChatService` 使用多 Agent 串联：

1. `MCPToolsAgent`：先执行 MCP 工具调用
2. `ComponentToolsAgent`：基于 `component_tools_for_backend` 与 MCP 结果决定是否组装组件工具调用
3. `ResponseGenerationAgent`：生成最终回答并输出 SSE

关键文件：

- `app/services/chat/chat_service.py`
- `app/agents/component_tools_agent.py`

## 4. 与流式响应的关系

聊天接口为 `POST /api/chat/stream`，返回 `text/event-stream`。

组件工具相关结果会并入 assistant 消息结构中：

- `component_tool_calls`
- `component_tool_calls_duration`
- `token_stats`（包含组件工具阶段）

最终在 `done` 事件中汇总耗时与统计字段。

## 5. 与旧方案差异

以下描述不再适用于当前代码：

- `component_tool_names`（已替换为 `component_tools_for_backend`）
- `app/services/chat_service.py`（路径已拆分为 `app/services/chat/chat_service.py`）
- 通过单函数 `_call_llm_with_component_tools` 的旧流程描述

## 6. 对接建议

- 前端应传完整 `ComponentToolConfig`，避免只传组件名；
- 新增组件时，需确保前端 schema 文件可被 `ComponentSchemaService` 访问；
- 若组件未命中触发条件，不会进入组件工具调用阶段。
