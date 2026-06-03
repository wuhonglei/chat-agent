# Agent 应用可观测性指标与实现方案 — 深度调研报告

> 2025 年 6 月 · 深度调研 · 技术报告
>
> 全面梳理 AI Agent 应用在可观测性方面的核心指标体系、技术实现方案与工具选型建议，覆盖性能监控、质量评估、成本追踪、业务分析等维度，为生产环境 Agent 系统的稳定运行提供参考。

**标签：** `AI Agent` `可观测性` `链路追踪` `OpenTelemetry` `生产监控` `成本优化`

---

## 目录

- [1. 概述](#1-概述)
  - [1.1 为什么需要 Agent 可观测性](#11-为什么需要-agent-可观测性)
  - [1.2 调研范围](#12-调研范围)
- [2. 可观测指标](#2-可观测指标)
  - [2.1 性能指标](#21-性能指标)
  - [2.2 质量指标](#22-质量指标)
  - [2.3 成本指标](#23-成本指标)
  - [2.4 业务指标](#24-业务指标)
  - [2.5 基础设施指标](#25-基础设施指标)
- [3. 实现方案](#3-实现方案)
  - [3.1 链路追踪](#31-链路追踪)
  - [3.2 指标采集](#32-指标采集)
  - [3.3 结构化日志](#33-结构化日志)
  - [3.4 评估体系](#34-评估体系)
  - [3.5 告警策略](#35-告警策略)
- [4. 工具对比](#4-工具对比)
  - [4.1 专用 Agent 可观测性工具](#41-专用-agent-可观测性工具)
  - [4.2 开源方案](#42-开源方案)
  - [4.3 APM 工具扩展](#43-apm-工具扩展)
- [5. 最佳实践](#5-最佳实践)
  - [5.1 接入实践](#51-接入实践)
  - [5.2 采样策略](#52-采样策略)
  - [5.3 成本控制](#53-成本控制)
- [6. 总结与建议](#6-总结与建议)

---

## 1. 概述

### 1.1 为什么需要 Agent 可观测性

AI Agent 与传统软件系统存在本质差异。传统系统通常是确定性的——相同的输入产生相同的输出，故障模式明确（HTTP 500、超时、异常）。而 Agent 系统是非确定性的，其内部执行链路复杂：接收用户请求 → 意图识别 → 工具选择 → 多轮 LLM 调用 → 工具执行 → 结果合成 → 响应生成。每一步都可能引入不确定性，且错误可能在多轮交互后才会显现。

> **⚠️ 核心挑战**
>
> 63% 的 AI Agent 在复杂多步骤任务中失败。这些失败往往不会在单个 LLM 调用层面表现出来，而是在跨轮次的状态累积和工具调用链中悄然发生。传统的 APM 工具可以看到某个请求返回了 HTTP 200，但无法判断 Agent 是否在第 3 步选择了错误的工具，导致第 8 步产生了错误答案。

Agent 可观测性的核心目标是回答以下关键问题：

- **发生了什么**：Agent 执行了哪些步骤？选择了哪些工具？每次 LLM 调用的输入输出是什么？
- **为什么发生**：某个决策背后的推理过程是什么？上下文窗口中的信息如何影响决策？
- **性能如何**：每个步骤的延迟是多少？Token 消耗情况？整体成本如何？
- **质量如何**：输出是否准确？是否存在幻觉？是否遵循了业务规则？
- **何时预警**：如何在问题影响用户之前发现异常？

### 1.2 调研范围

本报告涵盖 Agent 可观测性的以下核心维度：

- **指标体系**：覆盖性能、质量、成本、业务和基础设施五个维度的核心指标
- **实现方案**：链路追踪、指标采集、结构化日志、评估体系和告警策略
- **工具对比**：商业工具、开源方案和 APM 平台的对比分析
- **最佳实践**：生产环境的接入实践、采样策略和成本控制方法

---

## 2. 可观测指标

Agent 可观测指标可分为五个维度。每个维度对应不同的监控目标和数据采集方式。

### 2.1 性能指标

性能指标关注 Agent 系统的响应速度和资源利用情况。

| 指标 | 说明 | 类型 |
|------|------|------|
| **TTFT** (Time to First Token) | 用户发送请求到看到第一个响应 Token 的时间，直接影响交互体验。建议 < 500ms。 | `HISTOGRAM` |
| **TPOT** (Time Per Output Token) | 模型生成阶段每个 Token 的平均耗时，反映生成速度。 | `HISTOGRAM` |
| **Total Latency** | 完整请求处理时间，包括所有 LLM 调用、工具执行和状态管理。 | `HISTOGRAM` |
| **LLM Call Duration** | 单次 LLM 推理调用耗时，区分 Prefill（输入处理）和 Decode（输出生成）阶段。 | `HISTOGRAM` |
| **Tool Call Duration** | 工具调用执行耗时，按工具类型分组统计。 | `HISTOGRAM` |
| **Throughput** | 系统并发处理能力，包括请求/秒和 Token/秒两个维度。 | `GAUGE` |

> **💡 关键洞察**
>
> 对于对话式交互，TTFT 比 Total Latency 更重要。用户在 200ms 内看到第一个字，比等待 50ms 后突然停顿的体验要好得多。而对于文档处理类批量任务，Tokens Per Second 才是核心指标。

### 2.2 质量指标

质量指标评估 Agent 输出的准确性、安全性和可靠性。

| 指标 | 说明 | 类型 |
|------|------|------|
| **Hallucination Rate** | 输出中包含虚构或错误信息的比例。可通过 LLM-as-Judge 或规则引擎检测。 | `GAUGE` |
| **Groundedness Score** | 输出内容与检索上下文的一致程度，RAG 系统核心指标。 | `GAUGE` |
| **Intent Resolution** | Agent 正确识别用户意图的比例。 | `GAUGE` |
| **Tool Call Accuracy** | Agent 选择正确工具并传入正确参数的比例。 | `GAUGE` |
| **Response Completeness** | 输出是否完整回答了用户问题，无遗漏关键信息。 | `GAUGE` |
| **Safety Score** | 输出安全性评分，检测有害内容、PII 泄露等。 | `GAUGE` |

### 2.3 成本指标

成本指标是 Agent 系统运维的核心关注点，LLM API 调用通常占据运营成本的主要部分。

| 指标 | 说明 | 类型 |
|------|------|------|
| **Token Usage** | 按 Input/Output 分别统计的 Token 消耗量，区分不同模型。 | `COUNTER` |
| **Cost Per Request** | 单次请求成本，可按 Agent、模型、用户维度细分。 | `HISTOGRAM` |
| **Cost Per Conversation** | 完整多轮对话的总成本，用于预算规划和异常检测。 | `HISTOGRAM` |
| **Context Window Utilization** | 上下文窗口使用率，90% 以上意味着接近截断风险。 | `GAUGE` |
| **Cache Hit Rate** | Prompt 缓存命中率，高命中率可显著降低成本。 | `GAUGE` |
| **Daily/Monthly Budget** | 累计消耗与预算对比，用于成本控制和告警触发。 | `COUNTER` |

### 2.4 业务指标

业务指标连接 Agent 行为与用户价值和商业目标。

| 指标名称 | 说明 | 采集方式 |
|----------|------|----------|
| Task Success Rate | Agent 成功完成任务的比例 | 用户反馈 + 自动评估 |
| Escalation Rate | 转人工处理的比例 | 业务系统事件 |
| Conversation Turns | 平均对话轮次 | Session 追踪 |
| User Satisfaction | 用户满意度评分 | 显式反馈 + 隐式信号 |
| Resolution Time | 问题平均解决时间 | Session 持续时间 |
| Retry Rate | 用户重复提问的比例 | 对话分析 |

### 2.5 基础设施指标

基础设施指标确保 Agent 系统运行的底层资源充足。

- **CPU / GPU 利用率**：模型推理服务的资源消耗
- **内存使用**：上下文缓存和状态管理的内存占用
- **网络延迟**：LLM API 调用和工具服务的网络往返时间
- **队列深度**：待处理请求队列长度
- **Error Rate**：按错误类型（LLM 超时、工具失败、状态异常）分类的错误率
- **Rate Limit Hits**：触发 LLM Provider 限频的次数

---

## 3. 实现方案

### 3.1 链路追踪

链路追踪（Tracing）是 Agent 可观测性的核心能力。与传统微服务追踪不同，Agent 追踪需要捕获非确定性的决策链——Agent 可能在任意步骤选择不同工具、进行多轮 LLM 调用或进入循环。

#### Span 层次结构

一个典型的 Agent 执行链路包含以下 Span 层级：

```
# Agent Trace Span Hierarchy
invoke_agent support-router (INTERNAL, trace=t1)
│
├── chat gpt-4o (CLIENT)                    ← 意图识别与规划
│     gen_ai.usage.input_tokens = 1523
│     gen_ai.usage.output_tokens = 42
│     gen_ai.response.finish_reasons = ["tool_calls"]
│
├── execute_tool web_search (INTERNAL)       ← 工具调用 #1
│     gen_ai.tool.name = web_search
│     gen_ai.tool.call.arguments = {...}
│     gen_ai.tool.call.result = {...}
│
├── chat gpt-4o (CLIENT)                    ← 结果分析与决策
│     gen_ai.usage.input_tokens = 2841
│     gen_ai.usage.output_tokens = 128
│     gen_ai.response.finish_reasons = ["tool_calls"]
│
├── execute_tool query_database (INTERNAL)   ← 工具调用 #2
│
└── chat gpt-4o (CLIENT)                    ← 最终响应生成
      gen_ai.usage.input_tokens = 3120
      gen_ai.usage.output_tokens = 256
```

> **✅ OpenTelemetry GenAI Semantic Conventions**
>
> OpenTelemetry GenAI SIG（成立于 2024 年 4 月）已定义了 LLM 调用、Agent 执行和工具调用的标准 Span 类型和属性规范。采用这些规范可确保跨框架、跨工具的互操作性。核心 Span 类型包括：`chat`（LLM 调用）、`invoke_agent`（Agent 执行）、`execute_tool`（工具执行）、`create_agent`（Agent 创建）。

#### 三种接入方式

| 方式 | 实现复杂度 | 覆盖范围 | 适用场景 |
|------|-----------|----------|----------|
| Proxy-based | 低（分钟级） | 仅 LLM 调用 | 快速获得成本/延迟视图 |
| SDK Integration | 中（小时级） | 完整执行链路 | 生产环境深度追踪 |
| OpenTelemetry | 高（天级） | 全栈统一追踪 | 与现有可观测体系集成 |

### 3.2 指标采集

指标采集需要同时关注 Agent 特有指标和传统系统指标。推荐采用 OpenTelemetry + Prometheus 的标准化采集方案。

#### Prometheus 指标定义示例

```yaml
# 请求级指标
agent_requests_total{agent_name, status}          # Counter
agent_request_duration_seconds{agent_name}        # Histogram

# 模型推理指标
model_inference_duration_seconds{agent_name, model_id}  # Histogram
model_inference_calls_total{agent_name, model_id}       # Counter

# Token 指标
agent_token_usage_total{agent_name, model_id, token_type}  # Counter
agent_estimated_cost_dollars{agent_name, model_id}         # Counter

# 工具调用指标
agent_tool_calls_total{agent_name, tool_name, status}      # Counter
agent_tool_call_duration_seconds{agent_name, tool_name}    # Histogram

# 质量指标（由异步评估任务更新）
agent_quality_score{agent_name, metric_type}               # Gauge

# 对话指标
agent_conversation_turns{agent_name}                       # Histogram
agent_escalation_rate{agent_name}                          # Gauge
```

#### 采集架构

```
Agent Application  →  OTel SDK (GenAI Conventions)  →  OTel Collector  →  Prometheus / Mimir
                                                         ↓
                                                   Grafana Dashboards  ←  PromQL Queries  ←  AlertManager
```

### 3.3 结构化日志

结构化日志是追踪 Agent 行为的另一个关键手段。相比传统文本日志，结构化日志支持精确查询和关联分析。

#### 日志规范

```json
{
  "timestamp": "2025-06-01T12:34:56.789Z",
  "level": "INFO",
  "service": "support-agent",
  "trace_id": "abc123",
  "span_id": "def456",
  "event": "agent_request",
  "attributes": {
    "user_id": "user_456",
    "intent": "refund_request",
    "success": true,
    "latency_ms": 2345,
    "llm_calls": 3,
    "tool_calls": 2,
    "cost_usd": 0.045,
    "input_tokens": 1523,
    "output_tokens": 387,
    "model": "gpt-4o",
    "cache_hit": false,
    "conversation_turn": 3
  }
}
```

> **💡 关键字段**
>
> Agent 日志必须包含 `trace_id` 和 `span_id` 以实现与链路追踪的关联。业务字段（如 `user_id`、`conversation_id`）对于按用户维度分析成本和行为至关重要。

### 3.4 评估体系

评估（Evaluation）是 Agent 可观测性的独特维度——不仅要知道系统"是否在运行"，还要知道"运行得有多好"。评估分为离线评估和在线评估两个层面。

#### 离线评估（Offline Evaluation）

- **Golden Set Testing**：基于人工标注的标准测试集，在部署前验证 Agent 行为
- **A/B Testing**：对比不同 Prompt、模型或配置的效果差异
- **Regression Testing**：确保新版本不会破坏已有功能

#### 在线评估（Online Evaluation）

- **LLM-as-Judge**：使用独立 LLM 评估生产输出的质量
- **Rule-based Evaluation**：基于规则的安全性和合规性检查
- **Human-in-the-Loop**：人工抽样审核，校准自动评估的准确性

#### 核心评估维度

| 维度 | 指标 | 检测方法 |
|------|------|----------|
| 事实性 | Hallucination Rate | 上下文一致性检查、外部知识库验证 |
| 相关性 | Response Relevance | LLM-as-Judge 评分 |
| 完整性 | Response Completeness | 检查必需字段、任务完成度 |
| 安全性 | Safety Score | 有害内容检测、PII 扫描 |
| 工具使用 | Tool Accuracy | 工具选择正确性、参数有效性 |
| 指令遵循 | Instruction Adherence | 检查是否遵循系统指令和业务规则 |

### 3.5 告警策略

告警策略需要同时覆盖系统异常和 Agent 特有异常。传统的"HTTP 5xx 率 > 1%"告警对 Agent 系统远远不够。

#### 推荐的告警规则

```yaml
alerts:
  # 性能告警
  - name: high_latency_p95
    condition: p95(agent_request_duration_seconds) > 10s
    severity: warning
    notify: [slack]

  # 质量告警
  - name: hallucination_spike
    condition: hallucination_rate_1h > 0.05
    severity: critical
    notify: [slack, pagerduty]

  # 成本告警
  - name: cost_spike
    condition: hourly_cost > average_hourly_cost * 3
    severity: warning
    notify: [slack]

  - name: budget_threshold
    condition: daily_cost > daily_budget * 0.8
    severity: warning
    notify: [slack, email]

  # 可靠性告警
  - name: tool_error_rate
    condition: rate(agent_tool_calls_total{status='error'}[5m]) > 0.1
    severity: critical
    notify: [slack, pagerduty]

  # 业务告警
  - name: escalation_rate_high
    condition: escalation_rate_1h > 0.3
    severity: warning
    notify: [slack]
```

---

## 4. 工具对比

### 4.1 专用 Agent 可观测性工具

| 工具 | 类型 | 开源 | 最佳场景 | 起始价格 |
|------|------|------|----------|----------|
| **LangSmith** | LLM 可观测 + 评估 | 否 | LangChain/LangGraph 生态 | 免费（5K traces） |
| **Langfuse** | LLM 可观测 + 分析 | 是 | 自托管/数据主权要求 | 自托管免费 |
| **Braintrust** | 评估驱动开发 | 部分 | CI/CD 集成、评估工作流 | 免费（1M spans） |
| **Arize Phoenix** | AI 可观测 + 评估 | 是 | RAG 调试、生产监控 | 开源免费 |
| **Galileo** | 安全 + 评估 | 否 | 幻觉检测、合规监控 | 企业定价 |
| **Helicone** | LLM API 可观测 | 是 | 快速部署、成本监控 | 免费 |
| **AgentOps** | Agent 可观测 | 部分 | 自主 Agent 调试 | 免费 |

#### 工具选型建议

**🔗 LangChain/LangGraph 生态** — 首选：LangSmith
零配置集成，自动捕获 Agent 执行链、工具调用和中间输出。评估工作流、Prompt 管理和人工审核队列功能成熟。局限性：非 LangChain 框架需要手动埋点。

**🏠 自托管/数据主权要求** — 首选：Langfuse
开源可自托管，支持 Docker/K8s 部署。Session 追踪、成本归因、注释工作流完整。2026 年 1 月被 ClickHouse 收购，数据基础设施增强。局限性：评估工作流需要额外搭建。

**🧪 评估驱动开发** — 首选：Braintrust
最强大的 CI/CD 评估门禁工作流，Prompt 版本管理、实验对比 UI 优秀。免费层最慷慨（1M spans/月，无限用户）。局限性：云托管，无自托管选项。

**🔒 企业安全合规** — 首选：Galileo
亚 100ms 实时安全护栏，ChainPoll 幻觉检测、不确定性估计、上下文一致性评分。适用于金融、医疗等受监管行业。局限性：企业定价较高。

### 4.2 开源方案

#### OpenTelemetry 生态

OpenTelemetry 正成为 Agent 可观测性的行业标准。GenAI SIG 定义了 LLM 调用、Agent 执行和工具调用的语义规范。

**优势：**
- 供应商无关，避免锁定
- 与现有可观测体系统一
- 社区活跃，持续演进
- 支持 Traces/Metrics/Logs 三信号

**挑战：**
- GenAI 规范仍在开发阶段
- 框架级自动埋点仍在完善
- 需要自建 Collector 和后端
- 学习曲线较陡峭

#### OpenLLMetry

OpenLLMetry 是 OpenTelemetry 的 LLM 扩展，提供对主流 LLM Provider（OpenAI、Anthropic、Cohere、Bedrock 等）的自动埋点支持。

```python
# Python 快速接入
from opentelemetry.instrumentation.openai import OpenAIInstrumentor

OpenAIInstrumentor().instrument()
# 此后所有 openai.chat.completions.create() 调用自动产生 OTel Spans
```

### 4.3 APM 工具扩展

| 工具 | Agent 能力 | 优势 | 局限 |
|------|-----------|------|------|
| **Datadog** | LLM Observability 模块 | 与基础设施监控统一、决策路径图可视化 | 按 Span 计费、缺乏多轮因果分析 |
| **New Relic** | Agentic Platform (2026.02) | 多 Agent 系统可视化、50+ 集成 | 语义失败模式检测有限 |
| **Honeycomb** | 分布式追踪扩展 | AI 行为与系统健康关联分析 | 无内置 LLM 评估工作流 |
| **Grafana** | Tempo + Prometheus + Loki | 开源可定制、成本可控 | 需自建和配置 |

> **⚠️ 选型注意事项**
>
> 传统 APM 工具（Datadog、New Relic）的优势在于与现有基础设施监控的统一，但在 Agent 特有的多轮因果分析、评估工作流和失败模式检测方面存在明显不足。建议将专用 Agent 可观测工具与 APM 工具结合使用——前者负责 Agent 行为分析，后者负责基础设施监控。

---

## 5. 最佳实践

### 5.1 接入实践

1. **从第一天开始埋点** — 不要等到生产环境出问题才考虑可观测性。在开发阶段就接入追踪框架，确保所有 LLM 调用、工具执行和状态转换都被记录。

2. **使用标准语义规范** — 采用 OpenTelemetry GenAI Semantic Conventions 定义的属性命名和 Span 类型，确保跨团队、跨工具的互操作性。

3. **建立统一的 Trace ID 传播** — 在 Agent 系统的所有组件（LLM 调用、工具服务、数据库、消息队列）之间传递 Trace Context，确保端到端链路完整。

4. **捕获关键业务上下文** — 在 Span 属性中记录 `user_id`、`conversation_id`、`session_id` 等业务标识，支持按用户/会话维度的成本和行为分析。

5. **分离环境和版本** — 使用不同的 project 名称或版本标签区分 dev、staging 和 production 环境，避免测试数据污染生产监控。

### 5.2 采样策略

Agent 系统的追踪数据量可能非常庞大（一个复杂 Agent 执行可能产生数百个 Span），合理的采样策略对于控制成本至关重要。

| 采样策略 | 机制 | 适用场景 |
|----------|------|----------|
| Head-based Sampling | 在 Trace 起始处决定采样率 | 高流量场景，简单高效 |
| Tail-based Sampling | 完整收集后根据特征决策 | 保留异常/慢请求，丢弃正常请求 |
| Error-biased Sampling | 错误 Trace 100% 保留 | 故障排查优先场景 |
| Cost-biased Sampling | 高成本 Trace 100% 保留 | 成本优化分析场景 |

> **💡 Agent 采样特殊考虑**
>
> Agent 执行是一个 Span 层次结构——采样丢弃的是完整的 Agent 执行，而不是单个调用。如果 `tracesSampleRate` 低于 1.0，你可能丢失完整的 Agent 执行记录。建议使用 `tracesSampler` 对 Agent 路由保持 100% 采样，其他路由按基准采样。

### 5.3 成本控制

LLM API 成本是 Agent 系统的主要运营支出，有效的成本监控和优化至关重要。

#### 成本控制策略

- **实时成本追踪**：每次 LLM 调用后立即计算成本并更新累计指标
- **预算告警**：设置日/周/月预算阈值，达到 80% 时预警
- **成本归因**：按 Agent、模型、用户、功能模块细分成本
- **异常检测**：自动识别成本突增（如 Prompt 变更导致 Token 消耗翻倍）
- **模型路由**：根据任务复杂度自动选择成本最优的模型
- **缓存优化**：Prompt 缓存可减少 20-30% 的重复 Token 消耗

#### OTel Collector 作为策略层

利用 OTel Collector 的 Processor 能力，在数据离开网络前实现：

- PII 脱敏：从 Span 事件中移除敏感信息
- 尾部采样：仅保留满足条件（延迟阈值、错误状态）的 Trace
- 数据增强：添加用户元数据、环境标签
- 数据路由：Token 指标发送给 Prometheus，完整 Trace 发送给 Tempo，成本数据发送给数据仓库

---

## 6. 总结与建议

### 核心结论

> **✅ 关键发现**
>
> 1. **Agent 可观测性 ≠ LLM 监控**：Agent 系统的失败模式出现在多步骤因果链中，而非单个调用层面。需要 Session 级别的全链路追踪。
> 2. **OpenTelemetry 正在成为标准**：GenAI Semantic Conventions 提供了 LLM 调用、Agent 执行和工具调用的标准 Span 类型和属性规范。
> 3. **评估是可观测性的必要组成**：仅知道系统"在运行"不够，还需要知道"运行得有多好"。离线 + 在线评估形成质量闭环。
> 4. **成本监控是核心需求**：Token 消耗和 API 成本是 Agent 系统的主要运营支出，需要实时追踪和预算控制。

### 选型决策矩阵

| 场景 | 推荐工具 | 部署方式 | 关键理由 |
|------|----------|----------|----------|
| LangChain/LangGraph 生态 | LangSmith | SaaS | 零配置集成，生态深度最佳 |
| 数据主权/自托管要求 | Langfuse | Self-hosted | 开源、可 Docker/K8s 部署 |
| 评估驱动 + CI/CD | Braintrust | SaaS | 最强大的评估门禁工作流 |
| RAG 系统调试 | Arize Phoenix | Both | 检索评估、嵌入空间可视化 |
| 快速部署/成本监控 | Helicone | Both | 一行代码集成，分钟级部署 |
| 企业安全合规 | Galileo | SaaS | 亚 100ms 实时安全护栏 |
| 已有 Datadog 生态 | Datadog LLM | SaaS | 与基础设施监控统一 |
| 开源定制需求 | OTel + Grafana | Self-hosted | 完全可控，无供应商锁定 |

### 实施路线图建议

1. **Phase 1：基础可观测（1-2 周）** — 接入 OTel SDK 或专用工具 SDK，实现 LLM 调用和工具执行的自动追踪。部署基础 Grafana 面板监控延迟、错误率和 Token 消耗。

2. **Phase 2：质量评估（2-4 周）** — 建立离线评估集（Golden Set），接入 LLM-as-Judge 在线评估，设置幻觉检测和质量告警规则。

3. **Phase 3：成本优化（持续）** — 实现按 Agent/模型/用户的成本归因，设置预算告警，优化模型路由和缓存策略。

4. **Phase 4：高级分析（持续）** — 建立失败模式聚类、根因分析自动化、A/B 测试框架，形成完整的可观测性闭环。

### 最终建议

Agent 可观测性不是可选的附加功能，而是生产部署的必要基础设施。没有可观测性，你无法有效调试问题、控制成本、维护质量、满足 SLA 或持续改进系统。

无论选择哪种工具，以下原则是通用的：

- **追踪每个请求的完整链路**：从用户输入到最终响应的所有步骤
- **监控 AI 特有的质量指标**：幻觉率、事实性、工具使用准确性
- **实时追踪成本**：Token 消耗、API 费用、按维度归因
- **在问题影响用户前预警**：质量下降、成本突增、错误率升高
- **用丰富的上下文支持调试**：完整的输入输出、中间状态、决策理由

今天构建的可观测性能力，决定了你的 AI Agent 能否成功规模化——是稳定运行还是神秘失败，区别在于你是否能看清系统内部正在发生什么。

---

*Agent 应用可观测性指标与实现方案 — 深度调研报告*
*基于 2025 年行业最新实践与工具生态调研*
