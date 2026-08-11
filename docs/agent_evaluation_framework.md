# Agent 效果评估框架

> **文档状态**：早期盘点 / 规划稿。下表中「LLM-as-Judge ❌」「离线回归 pipeline ❌」等行**已过时**。
>
> 现网运维请读：
> - `backend/docs/EVAL_OPS.md` — Eval Worker、Bad Case 队列、`run_eval_gate` / replay
> - `backend/docs/batch_eval_worker_design.md` — 方案背景（文首有现网差异摘要）
> - `docs/agent_evaluator/rule_evaluator_design.md` — 实时规则评估器

## 1. 系统现状

### 1.1 已有基础设施

| 组件 | 状态 | 说明 |
|------|------|------|
| **Langfuse** | ✅ 已接入 | Trace 覆盖完整，含 chat-turn → 子 span 嵌套结构 |
| **Prometheus** | ⚠️ 基础版 | 仅 HTTP 请求指标 + 2 个进程级 Gauge（CPU/RSS） |
| **Langfuse Score** | ✅ 扩展中 | 含规则分、反馈、以及批量裁判写入的质量分 |
| **Langfuse Dashboard** | ✅ 2 个 | 工具分析 + 质量监控，共 10 个 widget |
| **测试集** | ⚠️ 有生产数据 | qa_baseline_100.csv / qa_classification.csv / qa_baseline_20_multi_turn.csv |
| **实时规则评估** | ✅ 已接入 | `app/evaluators/rule_evaluator.py`；见 `agent_evaluator/rule_evaluator_design.md` |
| **LLM-as-Judge 批量** | ✅ 已接入 | `eval_worker` + `BatchEvalService`；见 `EVAL_OPS.md` |
| **CI 评估门禁** | ✅ 已接入 | `scripts/run_eval_gate.py`（frozen / replay） |
| **Bad Case 复核队列** | ✅ 已接入 | `/api/eval/bad-cases*` |
| **RAG 评估框架** | ❌ 无 | RAGAS 等框架未接入 |

### 1.2 两种执行模式参数对比

| 维度 | 普通模式 (agent_mode=0) | Agent 模式 (agent_mode>0) |
|------|------------------------|--------------------------|
| MCP Servers | time, weather, tavily, code, context7, zread | file, skill_manager, shell, tavily, context7, zread |
| 最大 tool 迭代 | 10 次 | 90 次 |
| 附件处理 | 走 KB RAG → 注入 attachment_context | 跳过 RAG，注入文件清单，模型按需读取 |
| 系统提示词 | 无 skill_system / working_directory | 含 \<skill_system\> + \<working_directory\> 块 |
| tool 结果超限 | passthrough 全量返回 | 持久化到 .tool-results/ 替换为预览 |
| 迭代提示 | 每轮 apply_iteration_hints() | 无 |

**关键结论：评估必须按模式分组，不能混在一起看平均值。**

### 1.3 Langfuse Trace 结构

```
chat-turn (root span)
├── metadata: conversation_id, user_message_id, assistant_message_id, model_id, agent_mode
├── history-prepare        — 历史窗口准备（含窗口外摘要 LLM 子 generation）
├── memory-search          — Mem0 记忆检索
├── kb-rag-build           — KB RAG 组装（仅 agent_mode=0）
├── embedding              — 用户消息/文档向量化
├── title-generation       — 标题生成
├── {tool_name} (×N)       — 每个 MCP 工具调用（含 input/output/latency）
│   └── score: tool_success (BOOLEAN), tool_success:{tool_name} (BOOLEAN)
└── generation (auto)      — LLM 调用（langfuse.openai.AsyncOpenAI 自动采集）

离线同步 score:
├── message_status    — done=1.0 / stopped=0.5 / failed=0.0
└── user_feedback     — like=1.0 / dislike=0.0
```

---

## 2. 评估框架（三层模型）

### 第一层：结果评估（做没做成）

| 指标 | 计算方式 | 数据源 | 按模式分组 |
|------|----------|--------|-----------|
| **任务完成率** | message_status=done 占比 | Langfuse score | ✅ 必须 |
| **用户满意度** | user_feedback 的 like 率（排除 default） | Langfuse score | ✅ 必须 |
| **工具成功率** | tool_success 按 tool_name 分组 | Langfuse score | ✅ 必须 |
| **首次成功率** | 无 ERROR span 且 message_status=done | 需新建脚本 | ✅ 必须 |
| **输出准确性** | LLM-judge 完整性/准确性/相关性 1-5 分 | 需新建 | ✅ 必须 |
| **工具选择准确率** | 实际调用工具 vs 期望工具 | 需 testset 标注 | ✅ 必须 |

### 第二层：过程评估（怎么做成的）

| 指标 | 计算方式 | 数据源 | 按模式分组 |
|------|----------|--------|-----------|
| **规划效率** | 总 tool 调用次数 / 成功 tool 次数 | Langfuse trace span 计数 | ✅ 必须 |
| **重试率** | 同一 tool_name 连续 ERROR 后再调用 | trace span 序列分析 | ✅ 必须 |
| **路径效率** | 实际 tool 调用数 / 最优 tool 调用数 | 需人工标注 | ✅ 必须 |
| **自我纠错率** | ERROR 后成功恢复的比率 | trace span 模式检测 | ✅ 必须 |
| **多轮推进力** | 对话轮数 vs 任务完成度 | Langfuse session 聚合 | ✅ 必须 |
| **RAG 命中率** | kb-rag-build block_count >0 的比率 | Langfuse span output | 仅普通模式 |
| **工具编排效率** | 完成任务的平均步骤数 | Langfuse trace | 仅 Agent 模式 |
| **shell 安全拦截率** | blocked 命令占总 shell 调用比率 | tool_success + error_type | 仅 Agent 模式 |

### 第三层：系统评估（花了多少代价）

| 指标 | 计算方式 | 数据源 | 告警阈值建议 |
|------|----------|--------|-------------|
| **端到端延迟 P50/P95/P99** | trace duration 百分位（覆盖 run_chat_turn 全程：DB 读取 + memory search + RAG + LLM 迭代 + tool 执行 + 消息落库；不含 API 层 JWT 鉴权/请求校验/消息创建，约差 50-100ms） | Langfuse trace | P95 > 30s 告警 |
| **单次任务 Token 消耗** | generation usage 汇总 | Langfuse generation | > 10k token 标记 |
| **工具调用延迟分布** | tool span duration | Langfuse span | 单次 > 30s 告警 |
| **LLM 调用延迟** | generation span duration | Langfuse span | P95 > 15s 告警 |
| **错误率** | failed / total requests | Prometheus Counter | > 5% 告警 |
| **请求 QPS** | requests per second | Prometheus Histogram | — |
| **进程内存/CPU** | RSS / CPU time | Prometheus Gauge | RSS > 2GB 告警 |

---

## 3. 落地计划

### P0 — 立即可用（零代码）

在 Langfuse 已有 Dashboard 上补充图表：

1. **message_status 按 agent_mode 分组** — 对比两种模式的完成率差异
2. **tool_success 按 tool_name 的成功率热力图** — 快速定位哪些工具最不稳定
3. **trace latency P50/P95/P99 趋势** — 监控性能退化
4. **token usage 按 agent_mode 分组** — 对比两种模式的资源消耗

运行一次同步脚本确认 score 数据量：

```bash
cd backend
python scripts/sync_status_to_langfuse.py --prod --dry-run
python scripts/sync_feedback_to_langfuse.py --prod --dry-run
```

### P1 — 小改动（1-2 天）

#### 1. Prometheus 业务指标

在 `tool_executor.py` 和 `chat_orchestrator.py` 中增加：

```python
from prometheus_client import Counter, Histogram

# 对话级别
CHAT_TURNS_TOTAL = Counter(
    "chat_turns_total", "Total chat turns",
    ["agent_mode", "status"]  # status: done/stopped/failed
)
CHAT_TURN_DURATION = Histogram(
    "chat_turn_duration_seconds", "Chat turn duration",
    ["agent_mode"],
    buckets=[1, 2, 5, 10, 15, 30, 60, 120]
)

# 工具级别
TOOL_CALLS_TOTAL = Counter(
    "tool_calls_total", "Total tool calls",
    ["tool_name", "success"]  # success: true/false
)
TOOL_CALL_DURATION = Histogram(
    "tool_call_duration_seconds", "Tool call duration",
    ["tool_name"],
    buckets=[0.1, 0.5, 1, 2, 5, 10, 30]
)

# Token 用量
CHAT_TOKENS_TOTAL = Counter(
    "chat_tokens_total", "Total tokens consumed",
    ["agent_mode", "direction"]  # direction: input/output
)
```

#### 2. 补全 kb_rag_context_service 埋点

`app/services/chat/kb_rag_context_service.py` 目前没有 `observation_span` 调用，需增加：

```python
with observation_span("kb-rag-build", input={"query": query_text}) as span:
    # ... existing RAG logic ...
    if span:
        span.update(output={"block_count": len(blocks)})
```

#### 3. Langfuse Evaluator：message_status 自动同步

将离线批量同步改为事件驱动，在消息状态变更时实时写入 Langfuse score。

### P2 — 中等投入（1 周）

#### 1. 离线评估脚本

创建 `scripts/eval_agent_quality.py`：

```
输入: testset CSV（question + expected_tools + expected_keywords）
流程:
  1. 读取 testset
  2. 对每条 question 调用 POST /api/chat/stream
  3. 收集: 实际 tool 调用列表、响应内容、耗时
  4. 计算: 工具准确率、关键词命中率、响应质量
  5. 结果写入 Langfuse score + 本地 CSV 报告
输出: 按 category + agent_mode 分组的评估报告
```

测试集扩展：为现有 CSV 补充 `expected_tools` 和 `expected_keywords` 列。

#### 2. LLM-as-Judge 评估器

```
输入: question + answer
评估维度:
  - 完整性 (1-5): 回答是否覆盖问题所有方面
  - 准确性 (1-5): 信息是否正确，有无幻觉
  - 相关性 (1-5): 回答是否紧扣问题，无冗余
  - 工具使用合理性 (1-5): 工具选择和调用是否恰当
输出: 写入 Langfuse score: llm_judge_completeness / llm_judge_accuracy / llm_judge_relevance
```

#### 3. 安全评估

```
指标:
  - shell blocked 命令率: blocked / total shell calls
  - 敏感操作拦截率: 被 guardrail 拦截的 tool calls / total
  - 有害内容生成率: 需要内容安全检测（可接入第三方 API）
```

### P3 — 长期建设

1. **A/B 测试框架** — 在 trace metadata 中记录 experiment_id，支持模型/提示词对比
2. **RAG 评估管线** — 接入 RAGAS 框架，评估 retrieval precision/recall/faithfulness
3. **自动化回归 CI** — 在模型或提示词变更后自动运行评估脚本，对比 baseline
4. **实时告警** — Prometheus + Grafana 告警规则（已在远程服务器部署）

---

## 4. 关键文件索引

### 运行时埋点

| 文件 | 职责 |
|------|------|
| `backend/app/core/observability.py` | Langfuse 客户端初始化、span/score 工具函数 |
| `backend/app/core/process_metrics.py` | Prometheus 进程级 Gauge（CPU/RSS） |
| `backend/app/main.py` | 应用入口，初始化 Langfuse + Prometheus |
| `backend/app/services/chat/chat_orchestrator.py` | 主 trace 编排（chat-turn 及子 span） |
| `backend/app/services/base_service/llm_service.py` | LLM 调用（langfuse.openai 自动埋点） |
| `backend/app/agents/tool_executor.py` | 工具执行 + tool_success score |
| `backend/app/schemas/config.py` | LangfuseConfig 定义 |

### 离线脚本

| 文件 | 职责 |
|------|------|
| `backend/scripts/sync_feedback_to_langfuse.py` | 用户反馈 → Langfuse score |
| `backend/scripts/sync_status_to_langfuse.py` | 消息状态 → Langfuse score |
| `backend/scripts/create_dashboards.py` | 创建 Langfuse Dashboard |
| `scripts/import_to_langfuse.py` | 历史数据批量导入 Langfuse |
| `scripts/sync_scores_to_langfuse.py` | DB 消息状态 → Langfuse score |
| `scripts/langfuse_deep_analysis.py` | Trace 深度分析 |
| `scripts/fetch_langfuse_metrics.py` | Langfuse API 指标拉取 |
| `scripts/validate_langfuse_data.py` | 数据完整性校验 |

### 测试集

| 文件 | 内容 |
|------|------|
| `scripts/qa_baseline_100.csv` | 100 条生产问答（含 category、tool_names、response_time_ms） |
| `scripts/qa_classification.csv` | 带分类标签的问答数据 |
| `scripts/qa_baseline_20_multi_turn.csv` | 20 条多轮对话（按主题分组） |
| `docs/RAG/testset_generation.md` | L1/L2/L3 测试集生成流程设计（脚本未实现） |

### 文档

| 文件 | 内容 |
|------|------|
| `docs/agent_observability/langfuse_integration.md` | Langfuse 接入与运维手册 |
| `docs/langfuse_import_plan.md` | 历史数据导入计划 |
| `docs/langfuse_analysis_report.md` | Langfuse 分析报告 |
| `docs/RAG/testset_generation.md` | RAG 测试集生成流程 |
| `docs/agent_evaluation_framework.md` | 本文档 |

### 测试

| 文件 | 内容 |
|------|------|
| `backend/tests/core/test_observability.py` | 可观测性模块单元测试 |
| `backend/tests/services/chat/test_chat_orchestrator_tracing.py` | Trace 行为测试（成功/失败路径） |

---

## 5. 指标速查

```
第一层 — 结果评估
├── message_status 分布         → Langfuse score (已有)
├── user_feedback like 率       → Langfuse score (已有)
├── tool_success 按工具         → Langfuse score (已有)
├── 首次成功率                  → 需新建脚本
├── LLM-judge 质量评分          → 需新建
└── 工具选择准确率              → 需 testset 标注

第二层 — 过程评估
├── tool 调用效率               → Langfuse trace span 计数 (已有数据)
├── 重试/纠错率                 → trace span 序列分析 (需脚本)
├── 工具选择准确率              → 需 testset ground_truth
├── 多轮推进力                  → Langfuse session 聚合 (已有数据)
├── RAG 命中率                  → kb-rag-build span output (需补埋点)
└── shell 安全拦截率            → tool_success + error_type (已有数据)

第三层 — 系统评估
├── 延迟分布 P50/P95/P99       → Langfuse trace duration (已有)
├── Token 消耗                  → Langfuse generation usage (已有)
├── 资源占用 CPU/RSS            → Prometheus Gauge (已有)
├── 业务错误率                  → 需新增 Prometheus Counter
├── 工具调用 QPS/延迟           → 需新增 Prometheus Histogram
└── Token 用量趋势              → 需新增 Prometheus Counter
```
