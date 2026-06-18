# Chat Agent 面试准备 Roadmap

> 目标：围绕 5 份 Agent JD 的核心知识点，将项目已有能力转化为面试可讲故事，补齐关键差距，形成系统性的面试竞争力。
>
> 数据来源：`agent_jd_analysis.md`（5 份 JD 知识点）、`backend/app/` 项目代码

---

## 0. 面试竞争力全景图

### 项目已有能力 → JD 知识点映射

| JD 知识点 (A/B级)           | 项目现状                                     | 面试故事成熟度 |
| --------------------------- | -------------------------------------------- | -------------- |
| **A1. Agent 核心机制**       | 单 Agent ReAct 循环（ChatSessionAgent）、Tool Calling via MCP、状态机（ChatRoundStateMachine）、并行工具执行 | ★★★★☆ 链路完整，缺错误恢复叙事 |
| **A2. RAG + 向量数据库**     | pgvector + FAISS、kb_chunk_embedding、检索链路 | ★★★☆☆ 有基础，缺 Rerank 和效果量化 |
| **A3. LLM API + Prompt**    | DeepSeek/OpenAI 兼容、token 管理、context_compactor、结构化 prompt | ★★★★☆ 较成熟 |
| **A4. 多 Agent 协作**       | 实际为单 Agent + ReAct 循环，TitleGenerationAgent 是独立后台任务无协作；AGENTS.md 中的 ComponentToolsAgent/ResponseGenerationAgent 已移除合并 | ★★☆☆☆ 关键差距，需补充多 Agent 设计方案 |
| **A5. Python 后端工程**     | FastAPI + SQLModel + Alembic + Pydantic Settings + 分层架构 | ★★★★★ 核心优势 |
| **A6. PostgreSQL + 数据库** | SQLModel ORM、Alembic 迁移、pgvector、conversation_contexts | ★★★★☆ 较成熟 |
| **A7. 可观测性与监控**      | loguru 结构化日志 + observability.py          | ★★☆☆☆ 有日志，缺 trace 和指标 |
| **B8. 记忆与上下文管理**    | memory_service.py、context_compactor、context_summary | ★★★☆☆ 有基础，缺跨会话量化 |
| **B9. Agent 评测 (Eval)**   | 无                                            | ★☆☆☆☆ 关键差距 |
| **B10. 工程化部署**         | Dockerfile、start.sh、Nacos 配置中心          | ★★★☆☆ 缺 K8s 和 CI/CD |
| **B11. SSE 实时通信**       | SSE 流式响应、多种 event type (ack/delta/tool_start/done) | ★★★★★ 核心优势 |
| **B12. 成本与延迟优化**     | context_compactor 压缩、model_resolver 场景路由 | ★★★☆☆ 有基础，缺量化数据 |
| **B13. AI 辅助开发**        | 日常使用 Cursor/Copilot                       | ★★★★☆ |
| **B14. 小模型微调**         | 无                                            | ★☆☆☆☆ 了解即可 |
| **C15. MCP 协议**           | fastmcp 集成、MCPClientManager、5 个 MCP Server | ★★★★★ 项目核心差异化 |

---

## 1. 分阶段执行计划

### 阶段一：夯实核心叙事（1-2 周）

> 目标：让 A 级知识点全部达到"能讲 15 分钟深度故事"的水平

#### 1.1 Agent 核心机制 - 完善错误恢复与状态管理

**现状**：单 Agent ReAct 循环 + Tool Calling 已实现（ChatSessionAgent 内部多轮工具调用）
**差距**：错误恢复（retry/fallback）、Agent harness 的工程细节、面试时能讲清设计权衡
**行动项**：

- [ ] 梳理 `chat_orchestrator.py` 中的错误处理链路，整理为"错误恢复策略"叙事
  - 工具调用失败时的 fallback 逻辑
  - LLM 超时/限流时的重试与降级
  - 会话状态的 checkpoint 与恢复
- [ ] 补充 tool_call_policy.py 的策略设计思路文档（白名单、权限分级、超时控制）
- [ ] 整理 Agent 上下文工程的实践经验：context_compactor 的压缩策略、滑动窗口 vs 摘要

**面试话术模板**：
```
"我们的 Agent 系统采用单 Agent ReAct 循环架构...ChatSessionAgent 在一个
消息线程上多轮调用 LLM + MCP 工具，状态机驱动每轮从 GENERATING 到
TOOL_CALLING 到 DONE...当工具超时时会触发 fallback 到缓存结果或降级提示...
context_compactor 采用 token 预算 + 语义摘要的混合策略来管理上下文窗口..."
```

#### 1.2 RAG 链路 - 补 Rerank 和量化评估

**现状**：pgvector + FAISS 检索、kb_chunk_embedding 已有
**差距**：缺少 Rerank 环节、缺少检索效果量化指标
**行动项**：

- [ ] 在检索链路中增加 Rerank 步骤（用 cross-encoder 或 BGE-reranker）
- [ ] 构建 50+ 条 RAG 评测 case，对比 with/without rerank 的效果
- [ ] 记录关键指标：命中率、相关性评分、P50/P95 检索延迟
- [ ] 整理 Chunk 策略的设计选择（chunk size、overlap、metadata）

**面试话术模板**：
```
"我们的 RAG 链路是 embedding 检索 + cross-encoder rerank 的两阶段方案...
引入 rerank 后 top-5 命中率从 X% 提升到 Y%，但 P95 延迟增加了 N ms，
所以我们在效果和时延之间做了平衡..."
```

#### 1.3 LLM API 与 Prompt Engineering - 沉淀方法论

**现状**：已对接多个 provider、有结构化 prompt、token 管理
**差距**：prompt 设计方法论未体系化
**行动项**：

- [ ] 整理 `prompts/` 目录下所有 prompt，分类为：系统提示词、工具描述、输出格式化
- [ ] 总结 prompt 迭代经验：哪些改动带来了什么效果变化
- [ ] 整理 context window 管理策略：context_compactor 的压缩比、信息损失控制
- [ ] 整理 model_resolver 的场景路由设计：为什么不同场景用不同模型

---

### 阶段二：补齐关键差距（2-3 周）

> 目标：B 级知识点从"有基础"提升到"能讲清楚"，同时补齐 A 级关键差距

#### 2.1 可观测性体系 - 从日志到 Trace

**现状**：loguru 结构化日志、observability.py 基础埋点
**差距**：缺少端到端 trace、缺少 cost/latency 指标看板
**行动项**：

- [ ] 接入 Langfuse 或 OpenTelemetry，实现 请求→编排→LLM→工具→响应 全链路 trace
- [ ] 采集核心指标：input/output tokens、TTFR、工具耗时、错误分类
- [ ] 按 trace_id / conversation_id / user_id 关联查询
- [ ] 整理为面试故事："可观测体系的建设过程和收益"

**面试话术模板**：
```
"上线 Langfuse 后，我们能在 1 分钟内定位到慢请求的瓶颈是在 LLM 生成
还是在工具调用...通过 token 消耗分析发现 X% 的请求可以优化上下文长度..."
```

#### 2.2 记忆系统 - 量化跨会话收益

**现状**：memory_service.py 已实现跨会话记忆
**差距**：缺少命中率、重复问题下降等量化数据
**行动项**：

- [ ] 在 memory_service 中增加命中埋点：命中 / 未命中 / 误命中
- [ ] 定义"可使用记忆请求"的判定规则
- [ ] 构造 30+ 条记忆评测 case，量化命中率和误命中率
- [ ] 整理记忆架构设计：短期会话记忆 vs 长期用户记忆的分层策略

#### 2.3 Agent 评测体系 (Eval) - 从零到一

**现状**：无系统化评测
**差距**：这是 3/5 JD 提到的能力，属于关键差距
**行动项**：

- [ ] 设计评测框架：4 类场景覆盖（工具调用、RAG 问答、多轮对话、边界异常）
- [ ] 构建 100+ case 的评测集
- [ ] 实现自动评分（LLM-as-Judge + 规则校验）
- [ ] 首轮一致性校准：自动评分 vs 人工复核 >= 85%
- [ ] 建立回归机制：每次 prompt/模型变更自动跑评测

**面试话术模板**：
```
"我们建立了覆盖 4 类场景、100+ case 的自动评测体系...
采用 LLM-as-Judge + 规则校验的双层评分，与人工复核一致性达到 87%...
每次 prompt 变更都会触发回归评测，防止退化..."
```

#### 2.4 成本与延迟优化 - 量化优化成果

**现状**：context_compactor 压缩、model_resolver 场景路由
**差距**：缺少优化前后的量化对比数据
**行动项**：

- [ ] 测量 context_compactor 压缩前后的 token 消耗对比
- [ ] 测量场景路由（小任务用轻量模型）的成本节省比例
- [ ] 整理端到端延迟（TTFR）优化措施和效果
- [ ] 记录智能降级策略：限流时如何降级、错误时如何兜底

#### 2.5 多 Agent 协作 - 设计方案准备（A 级关键差距）

**现状**：项目实际为单 Agent + ReAct 循环（ChatSessionAgent），TitleGenerationAgent 只是独立后台任务无协作。
**差距**：4/5 JD 提到多 Agent 协作，属于面试高频话题。虽不是"已有能力的量化"，但必须有设计方案才能应对面试追问。
**行动项**：

- [ ] 研究 LangGraph / CrewAI / AutoGen 的核心概念，理解 DAG 编排、角色分工、共享状态
- [ ] 设计"如何将现有单 Agent 演进到多 Agent"的方案（面试时用）：
  - Planner Agent：接收用户请求，拆解为子任务
  - Executor Agent：执行具体工具调用（复用现有 MCPToolSession）
  - Reviewer Agent：校验执行结果，决定是否需要重试
- [ ] 准备"为什么当前选单 Agent 而不是多 Agent"的权衡分析（延迟、复杂度、场景适配）
- [ ] 了解 Agent 间通信模式：共享消息线程 vs 独立上下文 + 结果传递

---

### 阶段三：进阶区分（按需）

> 目标：对高薪岗位（40K+）的加分项做准备

#### 3.1 MCP 协议深度 - 差异化竞争力

**现状**：项目深度使用 MCP，有 5 个自研 MCP Server
**行动项**：

- [ ] 整理 MCP 协议设计：tool 注册、调用、结果缓存的完整机制
- [ ] 总结 MCP 与 Function Calling 的区别和适用场景
- [ ] 整理自研 MCP Server 的设计模式：何时用本地、何时用远程
- [ ] 了解 A2A 协议，准备"Agent 互操作"话题

#### 3.2 工程化部署 - 补 CI/CD 和 K8s

**行动项**：

- [ ] 完善 Dockerfile 多阶段构建
- [ ] 添加 GitHub Actions CI/CD pipeline（lint + test + build + deploy）
- [ ] 准备 K8s 部署方案（如果岗位要求）
- [ ] 整理 Nacos 配置中心的使用经验和设计决策

---

## 2. 面试高频问题准备清单

按 JD 知识点整理，每个问题应能回答 3-5 分钟：

### Agent 核心（必问）

1. "介绍一下你的 Agent 系统架构" → 画图 + 讲单 Agent ReAct 循环 + MCP 工具层 + Orchestrator 流程编排
2. "Tool Calling 是怎么实现的" → 从 prompt → function schema → 调用 → 结果注入
3. "遇到工具调用失败怎么办" → retry 策略 → fallback → 降级 → 错误分类
4. "上下文太长怎么办" → context_compactor 的压缩策略（滑动窗口 + 摘要 + token 预算）

### RAG（必问）

5. "你的 RAG 链路是怎样的" → embedding 检索 → rerank → 上下文注入
6. "怎么评估 RAG 效果" → 评测集 + 命中率 + 相关性评分
7. "Chunk 策略怎么选" → size/overlap/metadata 的权衡

### 工程化（高频）

8. "流式响应怎么实现的" → SSE 协议 → 多 event type → 前端增量渲染
9. "数据库怎么设计的" → conversation/message/context 模型 + pgvector
10. "怎么做可观测的" → 结构化日志 + trace + 成本指标

### 进阶（高薪岗位）

11. "如果要扩展到多 Agent 会怎么设计" → Planner/Executor/Reviewer 分工 + LangGraph DAG 编排 + 为什么当前选单 Agent
12. "怎么控制 LLM 调用成本" → 场景路由 + 上下文压缩 + 缓存 + 降级
13. "评测体系怎么建的" → 场景覆盖 + 自动评分 + 回归机制

---

## 3. 关键指标速查表（面试时引用）

面试时能说出具体数字，比泛泛而谈更有说服力。每个指标需要实际测量后填入：

| 指标                        | 目标值              | 当前值 | 状态 |
| --------------------------- | ------------------- | ------ | ---- |
| RAG top-5 命中率            | >= 80%              | 待测   | ⬜   |
| RAG 检索延迟 P95            | <= 400ms            | 待测   | ⬜   |
| Eval case 数量              | >= 100              | 0      | ⬜   |
| Eval 自动评分一致性         | >= 85%              | 无     | ⬜   |
| 跨会话记忆命中率            | >= 60%              | 待测   | ⬜   |
| 记忆误命中率                | < 5%                | 待测   | ⬜   |
| context_compactor 压缩比    | 记录实际数据        | 待测   | ⬜   |
| 场景路由成本节省比例        | 记录实际数据        | 待测   | ⬜   |
| 端到端 TTFR                 | 记录 P50/P95        | 待测   | ⬜   |
| 工具调用成功率              | >= 95%              | 待测   | ⬜   |

---

## 4. 项目亮点提炼（面试开场/自我介绍用）

### 一句话定位
> "我做了一个完整的 AI Agent 对话平台，从 FastAPI 后端到 React 前端，
> 涵盖了单 Agent ReAct 循环、RAG 检索、MCP 工具生态、流式响应等核心能力。"

### 三个亮点故事（STAR 格式准备）

1. **Agent ReAct 循环与上下文工程**
   - S：长对话场景下工具调用多轮交互导致 token 暴涨，超出模型上下文窗口
   - T：设计一套可控的 Agent 多轮工具调用架构
   - A：ChatSessionAgent 内实现 ReAct 循环（状态机驱动：GENERATING→TOOL_CALLING→FINALIZING→DONE），配合 context_budget 控制（tool_context_limit_ratio=0.8）避免上下文溢出，超限时自动切换为最终应答轮次
   - R：工具调用轮次可控（普通模式 10 轮、Agent 模式 90 轮），上下文溢出问题解决

2. **MCP 工具生态**
   - S：需要对接多种外部能力（搜索、天气、代码执行、文件操作）
   - T：统一工具接入协议，降低接入成本
   - A：基于 MCP 协议自研 5 个 MCP Server，统一管理生命周期
   - R：新工具接入标准化，支持热重载和健康检查

3. **上下文工程与成本控制**
   - S：长对话 token 消耗过高，超出上下文窗口
   - T：在不损失关键信息的前提下控制 token 成本
   - A：context_compactor（滑动窗口+摘要）+ model_resolver 场景路由
   - R：token 消耗降低 X%，同时保持回答质量

---

## 5. 优先级总结

```
紧急 + 重要（立刻做）
├── 1.1 Agent 核心叙事完善（错误恢复 + 状态管理）
├── 1.2 RAG 补 Rerank + 评测数据
└── 1.3 Prompt 方法论沉淀

重要不紧急（2-3 周内）
├── 2.1 可观测性接入（Langfuse/OTel）
├── 2.2 记忆系统量化
├── 2.3 Eval 评测体系搭建
├── 2.4 成本优化数据量化
└── 2.5 多 Agent 协作设计方案（4/5 JD 提到，项目缺失，准备设计方案）

锦上添花（按需）
├── 3.1 MCP 协议深度 + A2A 了解
└── 3.2 CI/CD + K8s 部署
```

---

## 6. 每日检查

每天结束前问自己：

1. 今天推进了哪个知识点？能用 1 分钟讲清楚进展吗？
2. 今天有没有测量或记录新的数据指标？
3. 今天准备的面试故事，能否经得住"为什么这样做？""有没有更好的方案？"的追问？
