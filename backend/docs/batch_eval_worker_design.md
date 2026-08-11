# 分层采样评估 Worker 方案

> 目标：将"定时批量（凌晨 3 点）"的裁判模型评估设计为独立 worker，与现有规则评估器和 BadCaseItemDb 完整对接

---

## 一、整体架构

```
┌─────────────────────┐        ┌──────────────────────────────┐        ┌──────────┐
│  chat_orchestrator   │        │  evaluator worker (独立进程)   │        │ Langfuse │
│                     │        │                              │        │          │
│  用户请求 → Agent    │        │  APScheduler / cron 触发      │        │ 存 Trace │
│  → 规则评估器(实时)   │──写入──→│  ① 拉取 24h Trace            │──读取──→│ 存 Score │
│  → 写 Trace + Score  │        │  ② 去重（排除已评 Trace）      │        │          │
│  → rule_fail 入队    │        │  ③ 规则预筛                   │        │          │
│                     │        │  ④ 分层采样                   │        │          │
│  用户点踩 → 异步入队  │        │  ⑤ 调裁判模型                 │        │          │
│                     │        │  ⑥ 写回 Langfuse Score        │        │          │
│                     │        │  ⑦ 低分入 bad_case_items      │        │          │
└─────────────────────┘        └──────────────────────────────┘        └──────────┘
         │                                    │
         │                                    │
         └──────── PostgreSQL ────────────────┘
                  bad_case_items 表
```

### 为什么独立 worker

| 维度 | 放在业务服务器 | 独立 worker |
|------|-------------|------------|
| 资源隔离 | 裁判调用占业务 CPU/内存 | 独立容器，互不影响 |
| 故障隔离 | 裁判 API 超时可能拖慢主服务 | worker 挂了不影响用户 |
| 扩缩容 | 按并发用户扩 | 按 Trace 数据量扩 |
| 部署节奏 | 跟业务一起发 | 独立发版 |

---

## 二、分层采样详细设计

### 2.1 完整流程

```
输入: 过去 24h 的 Langfuse Trace（规则层已打过基础分）

Step 1 — 去重过滤
  排除已存在裁判分数的 Trace（避免与事件驱动的点踩评估重复）
  排除 message.status == "stopped"（用户主动取消）
  排除已入 bad_case_items 的 message_id

Step 2 — 规则预筛（不送裁判，直接打分）
  ┌─ 空回答 (valid_answer=false) → 直接入队 rule_fail，跳过裁判
  ├─ 极短回答 (< 10 字) → 标记 trivial，跳过裁判
  ├─ 纯闲聊 (无工具调用 + 无 RAG 检索) → 标记 N/A，跳过裁判
  └─ 有效 RAG / 工具回答 → 进入候选池

Step 3 — 特殊场景识别（100% 采样）
  ┌─ 用户点踩 (feedback.value == "thumb_down") → 100%
  ├─ 快速追问 (user 下一条消息 < 30s) → 100%
  ├─ 新 query 类型 (首次出现的 embedding 聚类中心) → 100%
  └─ 低分历史变体 (与 bad_case_items 中 query 相似度 > 0.85) → 100%

Step 4 — 风险分层（常规场景）
  ┌─ 高风险: 含 execute_code / file_write / shell 调用 → 抽 40%
  ├─ 中风险: 含 knowledge_search / web_search / RAG 检索 → 抽 15%
  └─ 低风险: 纯模型生成（无工具、无检索）→ 抽 5%

Step 5 — 裁判模型打分
  并发调用（控制 QPS），写回 Langfuse Score
  score < 3 分 → 入 bad_case_items (source=low_score)

Step 6 — 输出统计报告
  日志: 总 Trace 数、候选池大小、各层采样量、裁判调用量、低分率
```

### 2.2 采样量估算（日均 1000 轮有效对话）

```
全部 Trace:                    1000 条
  ├─ 去重过滤:                  -200 条 (已有裁判分数/用户取消)
  ├─ 规则预筛淘汰:              -200 条 (空回答/极短/闲聊)
  └─ 候选池:                     600 条
       ├─ 特殊场景 (100%):      ~100 条
       ├─ 高风险 (40%):          ~40 条 (假设 ~100 条高风险)
       ├─ 中风险 (15%):          ~60 条 (假设 ~400 条中风险)
       ├─ 低风险 (5%):            ~5 条 (假设 ~100 条低风险)
       └─ 合计裁判调用:          ~205 条/天

成本估算 (以 qwen3-max 为例):
  205 条 × ~2000 input tokens × ¥0.002/1K ≈ ¥0.82/天
  205 条 × ~200 output tokens × ¥0.006/1K ≈ ¥0.25/天
  合计: ~¥1/天，可忽略
```

---

## 三、与现有组件的对接

### 3.1 BadCaseItemDb 对接

现有 `BadCaseItemDb` 已支持三种 source：`rule_fail` / `low_score` / `thumb_down`。

worker 使用 `low_score` source 入队：

```python
# 评估 worker 中低分入队
bad_case_service.enqueue(
    source=BadCaseSource.LOW_SCORE,
    message_id=trace_message_id,
    conversation_id=trace_conversation_id,
    user_id=trace_user_id,
    query=query[:500],
    answer=answer[:1000],
    rule_scores=trace_rule_scores,      # 从 Trace 的规则 score 读取
    judge_scores={                       # 裁判分数快照
        "correctness": correctness_score,
        "completeness": completeness_score,
        "coverage": coverage_rate,
        "missing_points": missing_points,
    },
    trace_id=trace_id,
)
```

去重逻辑已内置于 `BadCaseService.enqueue()`：同一 `message_id + source` 不重复入队。

### 3.2 规则评估器对接

规则评估器（`app/evaluators/rule_evaluator.py`）在实时链路中已写入 Langfuse Score：
- `valid_answer` (BOOLEAN)
- `tool_whitelist_ok` (BOOLEAN)
- `tool_call_count` (NUMERIC)
- `tool_loop_detected` (BOOLEAN)

worker 从 Langfuse Trace 的 scores 字段读取这些值，不需要重新计算。

### 3.3 与事件驱动评估的去重

点踩事件驱动（`app/api/message.py` 中 `_enqueue_thumb_down_bad_case`）会实时调裁判并入队。
worker 拉取 Trace 时需排除：

```python
# Step 1 去重: 排除已有裁判分数的 Trace
def should_skip(trace: dict, existing_bad_case_ids: set[str]) -> bool:
    # 1. 已有裁判分数（事件驱动已评过）
    scores = trace.get("scores", {})
    if any(s.get("name", "").startswith("judge_") for s in scores):
        return True
    # 2. 已在 bad_case_items 中
    meta = trace.get("metadata", {})
    if meta.get("message_id") in existing_bad_case_ids:
        return True
    return False
```

### 3.4 Langfuse Score 对接

裁判分数写回 Langfuse，命名为 `judge_correctness` / `judge_completeness`：

```python
from app.core.observability import get_langfuse

client = get_langfuse()
client.score(
    trace_id=trace_id,
    name="judge_correctness",
    value=correctness_score,   # 1-5
    data_type="NUMERIC",
    comment=json.dumps({"missing_points": missing_points}),
)
client.score(
    trace_id=trace_id,
    name="judge_completeness",
    value=completeness_score,  # 1-5
    data_type="NUMERIC",
)
```

---

## 四、数据库新增表：eval_run_logs

记录每次评估运行的统计信息，用于监控和回溯。

```python
"""评估运行日志：记录每次定时评估的执行情况。"""

from datetime import datetime
from sqlalchemy import JSON as SQLJSON, Column, DateTime, Integer, String, Text
from sqlmodel import Field, SQLModel
from app.utils.common import gen_uuid
from app.utils.date import get_datetime_now


class EvalRunLog(SQLModel, table=True):
    """每次评估运行的统计记录"""

    __tablename__ = "eval_run_logs"

    id: str = Field(
        default_factory=gen_uuid, primary_key=True, index=True, max_length=36
    )
    run_type: str = Field(
        max_length=32,
        default="scheduled",
        description="运行类型: scheduled(定时) / manual(手动触发)",
    )
    started_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    finished_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True)),
    )
    status: str = Field(
        default="running",
        max_length=16,
        description="运行状态: running / success / failed",
    )

    # ── 采样统计 ──
    total_traces: int = Field(default=0, description="拉取到的 Trace 总数")
    after_dedup: int = Field(default=0, description="去重后的 Trace 数")
    candidate_pool: int = Field(default=0, description="规则预筛后的候选池大小")
    sampled_count: int = Field(default=0, description="实际送裁判的数量")
    sample_breakdown: dict = Field(
        default_factory=dict,
        sa_type=SQLJSON,
        description="分层采样明细: {special: N, high: N, medium: N, low: N}",
    )

    # ── 裁判统计 ──
    judge_success: int = Field(default=0, description="裁判成功打分数量")
    judge_failed: int = Field(default=0, description="裁判调用失败数量")
    low_score_count: int = Field(default=0, description="低分(<3)入 bad case 的数量")

    # ── 错误信息 ──
    error_message: str | None = Field(
        default=None, sa_column=Column(Text), description="运行失败时的错误信息"
    )
```

---

## 五、代码结构

```
backend/
├── app/
│   ├── evaluators/
│   │   ├── __init__.py
│   │   ├── rule_evaluator.py           # 已有: 实时规则评估器
│   │   ├── judge_evaluator.py          # 新增: 裁判模型调用
│   │   └── sampler.py                  # 新增: 分层采样逻辑
│   │
│   ├── services/
│   │   └── eval/
│   │       ├── __init__.py
│   │       ├── bad_case_service.py     # 已有: bad case CRUD
│   │       ├── batch_eval_service.py   # 批量评估编排
│   │       └── judge_input_builder.py  # 从 last GENERATION / DB 组装裁判输入
│   │
│   ├── models/
│   │   └── eval_run_log_db.py          # 运行日志模型
│   │
│   └── schemas/
│       └── eval.py                     # 已有, 扩展 RunLog 相关 schema
│
├── eval_worker/
│   ├── __init__.py
│   ├── main.py                         # worker 入口, APScheduler 调度
│   └── config.py                       # worker 专用配置
│
├── scripts/
│   └── run_batch_eval.py               # 手动触发脚本 (方便调试)
│
├── alembic/
│   └── versions/
│       └── xxxx_add_eval_run_logs.py   # 新增迁移
│
└── tests/
    ├── evaluators/
    │   ├── test_sampler.py
    │   └── test_judge_evaluator.py
    └── services/eval/
        └── test_judge_input_builder.py
```

---

## 六、核心模块设计

### 6.1 分层采样器 (`app/evaluators/sampler.py`)

```python
"""分层采样器：从 Langfuse Trace 中按风险等级和特殊信号分层抽样。"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from app.utils.logger import logger


class RiskLevel(str, Enum):
    HIGH = "high"      # execute_code, file_write, shell
    MEDIUM = "medium"  # knowledge_search, web_search, RAG
    LOW = "low"        # 纯模型生成


# 高风险工具: 出错代价大（代码执行、文件操作、Shell）
HIGH_RISK_TOOLS = {
    "execute_code", "code_execute",
    "file_write", "file_mcp__write_file",
    "shell", "shell_mcp__execute_command",
}

# 中风险工具: 检索类，可能返回不相关内容
MED_RISK_TOOLS = {
    "knowledge_search", "web_search",
    "tavily_search", "tavily_extract",
    "context7_resolve-library-id", "context7_query-docs",
}

# 采样比例配置
SAMPLE_RATES = {
    RiskLevel.HIGH: 0.40,
    RiskLevel.MEDIUM: 0.15,
    RiskLevel.LOW: 0.05,
}

# 快速追问阈值（秒）
QUICK_FOLLOW_UP_THRESHOLD = 30


@dataclass
class SampleResult:
    """采样结果"""
    traces: list[dict] = field(default_factory=list)
    breakdown: dict[str, int] = field(default_factory=dict)
    skipped_dedup: int = 0
    skipped_rule_filter: int = 0


def classify_risk(trace: dict) -> RiskLevel:
    """根据 Trace 中的工具调用判断风险等级。"""
    meta = trace.get("metadata", {}) or {}
    # 从 Trace metadata 中读取工具名列表（规则评估时已写入）
    tool_names = set(meta.get("called_tools", []))

    # 备用: 从 Trace 的 observations/scores 推断
    if not tool_names:
        scores = trace.get("scores", [])
        tool_count = 0
        for s in scores:
            if s.get("name") == "tool_call_count":
                tool_count = s.get("value", 0)
                break
        # 有工具调用但不知道具体工具名，按中风险处理
        if tool_count > 0:
            return RiskLevel.MEDIUM
        return RiskLevel.LOW

    if tool_names & HIGH_RISK_TOOLS:
        return RiskLevel.HIGH
    if tool_names & MED_RISK_TOOLS:
        return RiskLevel.MEDIUM
    return RiskLevel.LOW


def is_effective_answer(trace: dict) -> bool:
    """规则预筛: 判断是否为有效回答（排除空回答/极短/闲聊）。"""
    scores = trace.get("scores", [])
    score_map = {s["name"]: s.get("value") for s in scores}

    # valid_answer = false → 空回答
    if score_map.get("valid_answer") is False:
        return False

    # 极短回答（< 10 字）
    output = trace.get("output", "")
    if isinstance(output, str) and len(output.strip()) < 10:
        return False

    # 纯闲聊: 无工具调用 + 无 RAG 检索 + 短回答
    tool_count = score_map.get("tool_call_count", 0)
    if tool_count == 0 and len(output.strip()) < 50:
        return False

    return True


def detect_special_signals(trace: dict, follow_up_traces: dict[str, dict]) -> bool:
    """检测特殊场景信号（100% 采样）。"""
    trace_id = trace.get("id", "")
    meta = trace.get("metadata", {}) or {}
    message_id = meta.get("message_id", "")

    # 1. 用户点踩
    scores = trace.get("scores", [])
    for s in scores:
        if s.get("name") == "user_thumb_down" and s.get("value") is True:
            return True

    # 2. 快速追问 (30s 内)
    if trace_id in follow_up_traces:
        return True

    # 3. 延迟异常高 (> 30s)
    latency = trace.get("latency", 0)
    if latency and latency > 30:
        return True

    return False


def stratified_sample(
    traces: list[dict],
    *,
    follow_up_traces: dict[str, dict] | None = None,
    seed: int = 42,
) -> SampleResult:
    """分层采样入口。

    Args:
        traces: Langfuse 拉取的原始 Trace 列表
        follow_up_traces: {trace_id: trace} 快速追问的 Trace 映射
        seed: 随机种子

    Returns:
        SampleResult 包含采样结果和统计
    """
    rng = random.Random(seed)
    follow_up_traces = follow_up_traces or {}
    result = SampleResult()

    # Step 1: 过滤无效 Trace
    valid_traces = []
    for t in traces:
        output = t.get("output")
        if not output or (isinstance(output, str) and not output.strip()):
            result.skipped_rule_filter += 1
            continue
        valid_traces.append(t)

    logger.info(
        "Sampler: filtered",
        total=len(traces),
        valid=len(valid_traces),
        skipped=len(traces) - len(valid_traces),
    )

    # Step 2: 规则预筛 + 分桶
    special_bucket: list[dict] = []
    risk_buckets: dict[RiskLevel, list[dict]] = {
        RiskLevel.HIGH: [],
        RiskLevel.MEDIUM: [],
        RiskLevel.LOW: [],
    }

    for t in valid_traces:
        # 规则预筛
        if not is_effective_answer(t):
            result.skipped_rule_filter += 1
            continue

        # 特殊场景 → 100% 采样
        if detect_special_signals(t, follow_up_traces):
            special_bucket.append(t)
            continue

        # 常规场景 → 按风险分层
        risk = classify_risk(t)
        risk_buckets[risk].append(t)

    # Step 3: 按比例采样
    sampled = list(special_bucket)  # 特殊场景全量
    result.breakdown["special"] = len(special_bucket)

    for risk_level, bucket in risk_buckets.items():
        rate = SAMPLE_RATES[risk_level]
        count = max(1, round(len(bucket) * rate)) if bucket else 0
        count = min(count, len(bucket))
        sampled_bucket = rng.sample(bucket, count) if count > 0 else []
        sampled.extend(sampled_bucket)
               result.breakdown[risk_level.value] = len(sampled_bucket)

    result.traces = sampled
    logger.info(
        "Sampler: sampled",
        special=result.breakdown.get("special", 0),
        high=result.breakdown.get("high", 0),
        medium=result.breakdown.get("medium", 0),
        low=result.breakdown.get("low", 0),
        total=len(sampled),
    )

    return result
```

### 6.2 裁判模型调用 (`app/evaluators/judge_evaluator.py`)

> **实现说明（与下方历史草稿有差异，以代码为准）**
>
> - 线上坏例发现 **不** 自动生成 `ground_truth`；无 gold 路径对齐离线 `SYSTEM_STEP2`：有【参考资料/工具返回内容】时以参考资料为事实依据。
> - 裁判输入由 `JudgeInputBuilder` 组装，**不是** `metadata.retrieved_contexts`（该字段未埋点）。
> - 上下文来源：同 `trace_id` 下最后一条 `type=GENERATION` 的 `input.messages`（含 `<query>` / `<user_memories>` / `<attachment_context>` / `role=tool`）；IO 缺失时回退 chat-turn I/O，reference 为空时可用 DB `content_blocks.tool_result` 兜底。
> - `judge_scores` 附带 `context_sources` / `notes` 便于排查。

```python
"""裁判模型：调用 LLM 对回答质量打分。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from app.utils.logger import logger


# 裁判 Prompt（无标准答案版本：对比检索内容）
JUDGE_PROMPT_NO_GOLD = """你是一个回答完整性评估器。

【用户问题】{query}
【检索到的参考内容】{retrieved_contexts}
【模型回答】{answer}

请判断：
1. 参考内容中与问题相关的关键信息点有哪些？（逐条列出）
2. 模型回答覆盖了哪些？遗漏了哪些？
3. 覆盖率 = 已覆盖数 / 总相关要点数
4. 评分 1-5：
   - 5: 覆盖率 >= 90%
   - 4: 覆盖率 >= 70%
   - 3: 覆盖率 >= 50%
   - 2: 覆盖率 < 50%
   - 1: 几乎未利用检索内容

输出 JSON: {{"score": int, "coverage": float, "missing_points": ["..."]}}"""


# 裁判 Prompt（有标准答案版本：用于评估集回归）
JUDGE_PROMPT_WITH_GOLD = """你是一个回答质量评估器。

【用户问题】{query}
【标准答案要点】{ground_truth}
【模型回答】{answer}

请判断：
1. 标准答案的要点有哪些？（逐条列出）
2. 模型回答覆盖了哪些？遗漏了哪些？是否包含错误信息？
3. 评分 1-5：
   - 5: 完全正确且覆盖所有要点
   - 4: 覆盖大部分要点，无错误
   - 3: 覆盖一半要点，无重大错误
   - 2: 覆盖不足一半或有明显错误
   - 1: 几乎未回答或完全错误

输出 JSON: {{"score": int, "correctness": int, "completeness": int, "missing_points": ["..."]}}"""


@dataclass
class JudgeResult:
    """裁判评分结果"""
    correctness: int = 0
    completeness: int = 0
    coverage: float = 0.0
    missing_points: list[str] | None = None
    raw_response: str = ""
    success: bool = True
    error: str | None = None


async def call_judge_model(
    *,
    query: str,
    answer: str,
    retrieved_contexts: str = "",
    ground_truth: str = "",
    llm_caller: Any,  # callable: async (messages) -> str
    temperature: float = 0.0,
) -> JudgeResult:
    """调用裁判模型打分。

    Args:
        query: 用户问题
        answer: 模型回答
        retrieved_contexts: 检索到的参考内容（思路 B）
        ground_truth: 标准答案要点（思路 A，可选）
        llm_caller: LLM 调用函数，签名 async (messages: list[dict]) -> str
        temperature: 温度，设为 0 减少随机性

    Returns:
        JudgeResult 评分结果
    """
    # 选择 Prompt
    if ground_truth:
        prompt = JUDGE_PROMPT_WITH_GOLD.format(
            query=query,
            ground_truth=ground_truth,
            answer=answer[:2000],  # 截断避免超长
        )
    else:
        prompt = JUDGE_PROMPT_NO_GOLD.format(
            query=query,
            retrieved_contexts=retrieved_contexts[:3000],
            answer=answer[:2000],
        )

    messages = [
        {"role": "system", "content": "你是一个严格的回答质量评估器。只输出 JSON，不要输出其他内容。"},
        {"role": "user", "content": prompt},
    ]

    try:
        raw = await llm_caller(messages)
        result = _parse_judge_response(raw)
        result.raw_response = raw
        return result
    except Exception as exc:
        logger.warning("Judge model call failed", error=exc, error_type=type(exc).__name__)
        return JudgeResult(success=False, error=str(exc))


def _parse_judge_response(raw: str) -> JudgeResult:
    """解析裁判模型的 JSON 输出。容错处理。"""
    # 提取 JSON 块
    text = raw.strip()
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # 尝试从文本中提取 JSON
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                data = json.loads(text[start:end])
            except json.JSONDecodeError:
                return JudgeResult(success=False, error="Failed to parse JSON")
        else:
            return JudgeResult(success=False, error="No JSON found in response")

    return JudgeResult(
        correctness=data.get("correctness", data.get("score", 0)),
        completeness=data.get("completeness", data.get("score", 0)),
        coverage=data.get("coverage", 0.0),
        missing_points=data.get("missing_points"),
    )
```

### 6.3 批量评估服务 (`app/services/eval/batch_eval_service.py`)

```python
"""批量评估编排：拉取 Trace → 分层采样 → 裁判打分 → 入 bad case 队列。"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlmodel import Session, select

from app.core.db import engine
from app.core.observability import get_langfuse
from app.evaluators.judge_evaluator import JudgeResult, call_judge_model
from app.evaluators.sampler import SampleResult, stratified_sample
from app.models.bad_case_item_db import BadCaseItemDb
from app.models.eval_run_log_db import EvalRunLog
from app.schemas.eval import BadCaseSource
from app.services.eval.bad_case_service import BadCaseService
from app.utils.date import get_datetime_now
from app.utils.logger import logger


# 裁判低分阈值
JUDGE_LOW_SCORE_THRESHOLD = 3
# 裁判并发控制
JUDGE_CONCURRENCY = 5
# Langfuse 拉取分页大小
TRACE_PAGE_SIZE = 50
# 裁判分数 Langfuse score 名称前缀
JUDGE_SCORE_PREFIX = "judge_"


class BatchEvalService:
    """批量评估编排服务。"""

    def __init__(
        self,
        *,
        llm_caller: Any,  # async (messages) -> str
        langfuse_client: Any | None = None,
    ):
        self.llm_caller = llm_caller
        self.langfuse = langfuse_client or get_langfuse()

    async def run(self, *, run_type: str = "scheduled") -> EvalRunLog:
        """执行一次完整的批量评估。

        Returns:
            EvalRunLog 运行日志
        """
        now = get_datetime_now()
        run_log = EvalRunLog(run_type=run_type, started_at=now, status="running")

        with Session(engine) as db:
            db.add(run_log)
            db.commit()
            db.refresh(run_log)

        try:
            await self._do_run(run_log)
            run_log.status = "success"
        except Exception as exc:
            run_log.status = "failed"
            run_log.error_message = str(exc)[:2000]
            logger.error("Batch eval failed", error=exc, error_type=type(exc).__name__)

        run_log.finished_at = get_datetime_now()
        with Session(engine) as db:
            db.add(run_log)
            db.commit()

        logger.info(
            "Batch eval finished",
            run_id=run_log.id,
            status=run_log.status,
            total_traces=run_log.total_traces,
            sampled=run_log.sampled_count,
            judge_success=run_log.judge_success,
            judge_failed=run_log.judge_failed,
            low_scores=run_log.low_score_count,
            duration_s=(run_log.finished_at - run_log.started_at).total_seconds()
            if run_log.finished_at
            else 0,
        )
        return run_log

    async def _do_run(self, run_log: EvalRunLog) -> None:
        """核心流程。"""
        # ① 拉取过去 24h Trace
        logger.info("Step 1: Fetching traces from Langfuse...")
        traces = self._fetch_traces(hours=24)
        run_log.total_traces = len(traces)
        logger.info(f"  Fetched {len(traces)} traces")

        if not traces:
            logger.info("No traces to evaluate, exiting")
            return

        # ② 去重: 排除已评过的 Trace
        logger.info("Step 2: Dedup...")
        traces = self._dedup_traces(traces)
        run_log.after_dedup = len(traces)
        logger.info(f"  After dedup: {len(traces)} traces")

        if not traces:
            return

        # ③ 分层采样
        logger.info("Step 3: Stratified sampling...")
        follow_ups = self._detect_follow_ups(traces)
        sample_result = stratified_sample(traces, follow_up_traces=follow_ups)
        run_log.candidate_pool = len(traces) - sample_result.skipped_rule_filter
        run_log.sampled_count = len(sample_result.traces)
        run_log.sample_breakdown = sample_result.breakdown

        if not sample_result.traces:
            logger.info("No traces sampled, exiting")
            return

        # ④ 裁判模型打分
        logger.info(f"Step 4: Judge evaluation ({len(sample_result.traces)} traces)...")
        judge_results = await self._batch_judge(sample_result.traces)
        run_log.judge_success = sum(1 for r in judge_results if r[1].success)
        run_log.judge_failed = sum(1 for r in judge_results if not r[1].success)

        # ⑤ 写回 Langfuse Score + 低分入 bad case 队列
        logger.info("Step 5: Writing scores and enqueueing low scores...")
        low_count = await self._write_results(judge_results)
        run_log.low_score_count = low_count

    def _fetch_traces(self, *, hours: int = 24) -> list[dict]:
        """从 Langfuse 拉取过去 N 小时的 Trace。"""
        if not self.langfuse:
            logger.warning("Langfuse client not available, cannot fetch traces")
            return []

        since = datetime.now(timezone.utc) - timedelta(hours=hours)
        all_traces: list[dict] = []
        page = 1

        while True:
            try:
                response = self.langfuse.fetch_traces(
                    limit=TRACE_PAGE_SIZE,
                    page=page,
                    from_timestamp=since,
                )
                traces = response.data if hasattr(response, "data") else []
                if not traces:
                    break
                all_traces.extend([t.dict() if hasattr(t, "dict") else t for t in traces])
                if len(traces) < TRACE_PAGE_SIZE:
                    break
                page += 1
            except Exception as exc:
                logger.warning("Failed to fetch traces", page=page, error=exc)
                break

        return all_traces

    def _dedup_traces(self, traces: list[dict]) -> list[dict]:
        """去重: 排除已有裁判分数或已在 bad case 队列中的 Trace。"""
        with Session(engine) as db:
            # 已入 bad case 的 message_id 集合
            existing = db.exec(
                select(BadCaseItemDb.message_id).where(
                    BadCaseItemDb.source.in_(
                        [BadCaseSource.LOW_SCORE.value, BadCaseSource.THUMB_DOWN.value]
                    )
                )
            ).all()
            existing_ids = {row for row in existing if row}

        deduped = []
        for t in traces:
            # 排除已有裁判分数
            scores = t.get("scores", [])
            if isinstance(scores, list):
                has_judge = any(
                    s.get("name", "").startswith(JUDGE_SCORE_PREFIX) for s in scores
                )
                if has_judge:
                    continue

            # 排除已在 bad case 队列
            meta = t.get("metadata", {}) or {}
            msg_id = meta.get("message_id", "")
            if msg_id and msg_id in existing_ids:
                continue

            # 排除用户取消的消息
            if meta.get("message_status") == "stopped":
                continue

            deduped.append(t)

        return deduped

    def _detect_follow_ups(self, traces: list[dict]) -> dict[str, dict]:
        """检测快速追问: 同一用户 30s 内连续发消息。"""
        # 按 session 分组，按时间排序
        sessions: dict[str, list[dict]] = {}
        for t in traces:
            sid = t.get("sessionId", "unknown")
            sessions.setdefault(sid, []).append(t)

        follow_ups: dict[str, dict] = {}
        for sid, session_traces in sessions.items():
            session_traces.sort(key=lambda t: t.get("timestamp", ""))
            for i in range(1, len(session_traces)):
                prev = session_traces[i - 1]
                curr = session_traces[i]
                prev_time = prev.get("timestamp")
                curr_time = curr.get("timestamp")
                if not prev_time or not curr_time:
                    continue
                # 计算时间差
                try:
                    if isinstance(prev_time, str):
                        from datetime import datetime as dt
                        prev_dt = dt.fromisoformat(prev_time.replace("Z", "+00:00"))
                        curr_dt = dt.fromisoformat(curr_time.replace("Z", "+00:00"))
                    else:
                        prev_dt = prev_time
                        curr_dt = curr_time
                    gap = (curr_dt - prev_dt).total_seconds()
                    if 0 < gap <= 30:
                        follow_ups[prev.get("id", "")] = prev
                except Exception:
                    continue

        return follow_ups

    async def _batch_judge(
        self, traces: list[dict]
    ) -> list[tuple[dict, JudgeResult]]:
        """并发调用裁判模型：先 JudgeInputBuilder 组装上下文，再 call_judge_model。"""
        semaphore = asyncio.Semaphore(JUDGE_CONCURRENCY)

        async def _judge_one(trace: dict) -> tuple[dict, JudgeResult]:
            async with semaphore:
                # 从 last GENERATION messages 解析 query/memories/RAG/工具结果
                judge_input = await asyncio.to_thread(
                    self.judge_input_builder.build_from_trace, trace
                )
                result = await call_judge_model(
                    query=judge_input.query,
                    answer=judge_input.answer,
                    reference_contexts=judge_input.reference_xml,
                    llm_caller=self.llm_caller,
                    context_sources=judge_input.source_flags,
                )
                return trace, result

        return list(await asyncio.gather(*[_judge_one(t) for t in traces]))

    async def _write_results(
        self, results: list[tuple[dict, JudgeResult]]
    ) -> int:
        """写回 Langfuse Score，低分入 bad case 队列。返回低分计数。"""
        low_count = 0

        with Session(engine) as db:
            bad_case_service = BadCaseService(db)

            for trace, judge_result in results:
                if not judge_result.success:
                    continue

                trace_id = trace.get("id", "")
                meta = trace.get("metadata", {}) or {}

                # 写回 Langfuse Score
                if self.langfuse:
                    try:
                        self.langfuse.score(
                            trace_id=trace_id,
                            name="judge_correctness",
                            value=judge_result.correctness,
                            data_type="NUMERIC",
                        )
                        self.langfuse.score(
                            trace_id=trace_id,
                            name="judge_completeness",
                            value=judge_result.completeness,
                            data_type="NUMERIC",
                        )
                    except Exception as exc:
                        logger.warning(
                            "Failed to write Langfuse score",
                            trace_id=trace_id,
                            error=exc,
                        )

                # 低分入 bad case 队列
                min_score = min(judge_result.correctness, judge_result.completeness)
                if min_score < JUDGE_LOW_SCORE_THRESHOLD:
                    low_count += 1
                    bad_case_service.enqueue(
                        source=BadCaseSource.LOW_SCORE,
                        message_id=meta.get("message_id"),
                        conversation_id=meta.get("conversation_id"),
                        user_id=trace.get("userId"),
                        query=str(trace.get("input", ""))[:500],
                        answer=str(trace.get("output", ""))[:1000],
                        judge_scores={
                            "correctness": judge_result.correctness,
                            "completeness": judge_result.completeness,
                            "coverage": judge_result.coverage,
                            "missing_points": judge_result.missing_points or [],
                        },
                        trace_id=trace_id,
                    )

            db.commit()

        return low_count
```

### 6.4 Worker 入口 (`eval_worker/main.py`)

```python
"""评估 Worker 入口：APScheduler 定时触发批量评估。"""

from __future__ import annotations

import asyncio
import signal
import sys
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

# 将 backend/ 加入 sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import settings
from app.core.db import engine
from app.core.observability import init_langfuse
from app.services.eval.batch_eval_service import BatchEvalService
from app.utils.logger import logger


# ── LLM 调用器 ──────────────────────────────────────────────
# 使用项目已有的 LLM 基础设施调裁判模型
async def judge_llm_caller(messages: list[dict]) -> str:
    """裁判模型调用器。使用配置中的 judge 场景模型。"""
    from openai import AsyncOpenAI

    from app.services.base_service.model_resolver import resolve_scenario

    llm_config = resolve_scenario("judge")
    client = AsyncOpenAI(
        api_key=llm_config.api_key,
        base_url=llm_config.api_base,
    )
    response = await client.chat.completions.create(
        model=llm_config.model_name,
        messages=messages,
        temperature=0.0,
        max_tokens=1024,
    )
    return response.choices[0].message.content or ""


# ── 定时任务 ──────────────────────────────────────────────────
async def run_scheduled_eval() -> None:
    """凌晨 3 点定时评估任务。"""
    logger.info("=== Scheduled batch eval started ===")
    service = BatchEvalService(llm_caller=judge_llm_caller)
    run_log = await service.run(run_type="scheduled")
    logger.info(
        "=== Scheduled batch eval finished ===",
        run_id=run_log.id,
        status=run_log.status,
    )


async def main() -> None:
    """Worker 主循环。"""
    init_langfuse()

    scheduler = AsyncIOScheduler(timezone="Asia/Shanghai")

    # 每天凌晨 3 点执行
    scheduler.add_job(
        run_scheduled_eval,
        trigger=CronTrigger(hour=3, minute=0),
        id="batch_eval",
        name="定时批量评估",
        replace_existing=True,
    )

    scheduler.start()
    logger.info("Eval worker started, scheduled: daily 03:00 CST")

    # 优雅退出
    stop_event = asyncio.Event()

    def _signal_handler() -> None:
        stop_event.set()

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _signal_handler)

    await stop_event.wait()
    scheduler.shutdown(wait=False)
    logger.info("Eval worker stopped")


if __name__ == "__main__":
    asyncio.run(main())
```

### 6.5 手动触发脚本 (`scripts/run_batch_eval.py`)

```python
"""手动触发批量评估（调试用）。

用法:
    uv run python scripts/run_batch_eval.py [--hours 24] [--dry-run]
"""

import asyncio
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.observability import init_langfuse
from app.services.eval.batch_eval_service import BatchEvalService


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--hours", type=int, default=24, help="拉取最近 N 小时的 Trace")
    parser.add_argument("--dry-run", action="store_true", help="只采样不调裁判")
    args = parser.parse_args()

    init_langfuse()

    # 复用 worker 的 LLM caller
    from eval_worker.main import judge_llm_caller

    service = BatchEvalService(llm_caller=judge_llm_caller)
    run_log = await service.run(run_type="manual")

    print(f"\nRun ID: {run_log.id}")
    print(f"Status: {run_log.status}")
    print(f"Total traces: {run_log.total_traces}")
    print(f"After dedup: {run_log.after_dedup}")
    print(f"Sampled: {run_log.sampled_count}")
    print(f"Breakdown: {run_log.sample_breakdown}")
    print(f"Judge success: {run_log.judge_success}")
    print(f"Judge failed: {run_log.judge_failed}")
    print(f"Low scores: {run_log.low_score_count}")


if __name__ == "__main__":
    asyncio.run(main())
```

---

## 七、配置扩展

在 `app/schemas/config.py` 中新增评估配置：

```python
class EvalWorkerConfig(BaseModel):
    """评估 Worker 配置"""

    enabled: bool = Field(default=False, description="是否启用评估 worker")
    schedule_cron: str = Field(
        default="0 3 * * *",
        description="定时任务 cron 表达式",
    )
    judge_model_scenario: str = Field(
        default="judge",
        description="裁判模型使用的 scenario（models.scenarios.judge）",
    )
    judge_concurrency: int = Field(default=5, description="裁判并发数")
    judge_low_score_threshold: int = Field(
        default=3, description="低分阈值（低于此分入 bad case 队列）"
    )
    sample_rate_high: float = Field(default=0.40, description="高风险采样比例")
    sample_rate_medium: float = Field(default=0.15, description="中风险采样比例")
    sample_rate_low: float = Field(default=0.05, description="低风险采样比例")
    quick_follow_up_threshold_s: int = Field(
        default=30, description="快速追问阈值（秒）"
    )
```

---

## 八、Docker Compose 新增服务

```yaml
# docker-compose.yml 新增
evaluator:
  build:
    context: ./backend
    dockerfile: Dockerfile
  command: ["uv", "run", "python", "-m", "eval_worker.main"]
  env_file: ./backend/.env
  environment:
    - APP__DEBUG=0
    - DATABASE__HOST=postgres
  depends_on:
    - backend
    - postgres
  restart: unless-stopped
  deploy:
    resources:
      limits:
        memory: 512M
        cpus: "0.5"
```

---

## 九、实施路径

| 步骤 | 动作 | 投入 | 产出 |
|------|------|------|------|
| 1 | 新增 `eval_run_logs` 表 + Alembic 迁移 | 0.5 天 | 运行日志模型 |
| 2 | 实现 `sampler.py`（分层采样逻辑） | 1 天 | 采样器 + 单元测试 |
| 3 | 实现 `judge_evaluator.py`（裁判调用） | 1 天 | 裁判模型封装 |
| 4 | 实现 `batch_eval_service.py`（编排） | 1.5 天 | 完整编排流程 |
| 5 | 实现 `eval_worker/main.py`（Worker 入口） | 0.5 天 | APScheduler 定时任务 |
| 6 | 手动触发脚本 + 本地联调 | 1 天 | 端到端跑通 |
| 7 | Docker Compose + 部署 | 0.5 天 | 独立容器运行 |
| 8 | 裁判校准（50 条人工精标） | 2 天 | 一致率 >= 85% |
| **合计** | | **~8 天** | 完整独立评估 Worker |

### 第一步优先做

1. 新增 `EvalRunLog` 模型 + 迁移
2. 实现 `sampler.py`，写单元测试（mock Trace 数据，验证分层比例）
3. 手动跑 `scripts/run_batch_eval.py`，看采样结果分布是否合理

---

## 十、风险与对策

| 风险 | 对策 |
|------|------|
| 裁判模型输出格式不稳定 | `_parse_judge_response` 多层容错；temperature=0 |
| Langfuse API 限流 | 分页拉取 + 重试；单次写回用 batch |
| 裁判调用超时 | asyncio.wait_for 包裹，单条超时不影响批次 |
| 与事件驱动评估重复 | Step 2 去重：排除已有 judge_ 分数的 Trace |
| 采样比例不合理 | 先 manual 跑一周看分布，再调整 sample_rate |
| worker 进程挂掉 | APScheduler coalesce_jobs=True，下次执行补上 |
