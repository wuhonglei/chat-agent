# chat-agent 是否适合使用 pydantic-ai

## 结论：不适合

---

## 一、编排逻辑深度定制 — 框架抽象层会成为障碍

项目有大量自研的编排策略，分布在 6+ 个模块中：

| 模块 | 职责 |
|------|------|
| `ToolCallGuardrail` | 熔断器机制，精确失败计数/同工具失败/无进展检测 |
| `ToolCallPolicy` | 查询相似度去重、URL 重叠检测、迭代次数限制 |
| `ToolBatchPlanner` | 路径冲突感知的并行工具分段执行 |
| `ContextCompactor` | 工具结果的 token 级压缩 |
| `ChatRoundStateMachine` | GENERATING → TOOL_CALLING → FINALIZING → DONE 状态机 |
| `ContentBlocksAggregator` | 思考块/工具块/文本块的流式聚合 |

pydantic-ai 的 `Agent.run()` 把 tool loop 内化了 —— 框架自动处理"调用工具→收集结果→继续生成"的循环。这意味着：

1. 无法在每轮工具调用前后插入自定义 guardrail/policy 逻辑
2. 流式 SSE 事件（tool_start/delta/content_block_done）的精细控制被框架接管
3. 工具结果的压缩、批处理、后处理等中间件无处挂载

项目的编排复杂度已经超出了 pydantic-ai 的设计边界。强行适配会导致大量 hook/monkey-patch，得不偿失。

---

## 二、基础设施已自建 — 重复建设无收益

pydantic-ai 的核心卖点：

| 卖点 | 项目现状 |
|------|----------|
| 结构化输出（Pydantic BaseModel） | 对话场景输出自由文本，不需要 |
| 类型安全的工具定义 | MCP 工具是动态注册的，非静态定义 |
| 依赖注入（deps_type） | 已有 FastAPI 的 Depends 体系 |
| 自动重试 + 输出校验 | 已有 LLM error handling + circuit breaker |

项目已在 `LLMService` 层面实现了 Langfuse 集成、错误分类、熔断、token 计算等能力。引入 pydantic-ai 不会带来增量价值，反而要处理两套 LLM 调用路径的兼容问题。

---

## 什么项目适合 pydantic-ai？

- 需要结构化输出的场景（信息抽取、分类、数据验证）
- 工具数量少且静态（3-10 个 Python 函数）
- 不需要精细控制 tool loop 的中间过程
- 新项目从零开始，没有现有 Agent 框架

当前项目恰好都不满足这些条件。

---

## 一句话总结

chat-agent 的核心价值在于深度定制的编排策略（guardrail/policy/batch/compaction），这些恰好是 pydantic-ai 抽象层会遮蔽而非增强的部分。迁移成本远大于收益，属于"用框架约束架构"而非"用框架加速开发"。
