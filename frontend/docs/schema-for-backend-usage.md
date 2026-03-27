# Schema 给后端使用说明（当前实现）

## 1. 结论

当前实现中，前端**不直接把 schema 放进聊天请求体**。
前端只传组件工具配置，后端根据组件名自行获取 schema：

- 请求字段：`componentToolsForBackend`
- 后端字段：`component_tools_for_backend`
- schema 拉取方：后端 `ComponentSchemaService`

## 2. 前端发送内容

`ChatRequest` 中组件字段（见 `src/interfaces/chat.ts`）：

- `componentToolsForBackend: Pick<ComponentToolRequestItem, "name" | "whenCondition" | "when">[]`

即每项包含：

- `name`
- `whenCondition`
- `when`

不包含 `schema` 本体。

## 3. 后端如何拿到 schema

后端收到聊天请求后，会在组件工具阶段通过 `ComponentSchemaService` 请求：

- `{component_schema_api_url}/{component_name}.json`

例如：

- `/component-schemas/weather.json`

并在服务端缓存（类级缓存）后继续用于组件工具调用与结果生成。

## 4. 为什么采用“后端拉取 schema”

相比“前端内联 schema”方案，当前实现的优点：

- 请求体更小；
- schema 版本由后端拉取时统一控制；
- 前端无需维护 schema 传输逻辑；
- 后端可统一做缓存与重试。

## 5. 文档边界

以下属于历史方案，不适用于当前代码：

- `component_tools` 请求字段；
- 前端把 `schema` 一并放入聊天请求体；
- 后端直接从请求体读取 `schema` 的示例代码。
