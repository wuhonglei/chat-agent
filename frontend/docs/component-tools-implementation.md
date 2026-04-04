# 组件工具实现说明（历史归档）

> 状态：历史文档（非现网）  
> 更新日期：2026-04-04

## 1. 为什么归档

仓库当前代码已不再包含本文档最初对应的组件工具链路（例如 `src/componentTools/*` 的运行时代码、`ChatRequest.componentToolsForBackend` 字段）。

因此本文档不再作为现网实现说明，仅保留为历史背景。

## 2. 当前现网应参考的文档

- 会话与 SSE 协议：`frontend/docs/conversation.md`
- 前端请求体字段：`frontend/docs/schema-for-backend-usage.md`

## 3. 与旧实现的关键差异

- 当前 `ChatRequest` 不包含 `componentToolsForBackend`。
- 当前后端 `ChatRequest` 不包含 `component_tools_for_backend`。
- 旧文档中“前端传组件规则、后端按字段拉取 schema”的描述不适用于现网。

## 4. 维护建议

若未来重新引入组件工具能力，请：

1. 先在代码中恢复并落地完整链路（前端类型、后端 schema、服务逻辑、回归测试）。
2. 再把本文档从“历史归档”改回“现网实现”，并补充最小可运行示例。
