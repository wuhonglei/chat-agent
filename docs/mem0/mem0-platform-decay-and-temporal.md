# Mem0 Platform 增值方案：Memory Decay 与 Temporal Reasoning

> 以下两个功能均为 Mem0 **Platform 专属**，OSS SDK（v2.0.14）未实现。
> OSS 代码中调用会直接抛 `ValueError`。
> 来源：官方博客 + 源码验证。

## 一、Memory Decay（记忆衰减）

博客：https://mem0.ai/blog/introducing-memory-decay-in-mem0

### 核心思想

**只影响搜索排序，不删除任何记忆。** 基于"最近被访问过的记忆更重要"这一假设。

### 实现机制

```
写入时：无变化，与正常流程完全一样

搜索时：
  1. 正常执行向量搜索，得到候选集
  2. 对每条候选记忆，读取其"最近访问时间戳"
  3. 根据距上次访问的时间间隔，计算一个缩放系数：
     - 刚访问过的 → 1.5× 加成
     - 很久没访问的 → 0.3× 衰减
     - 即：5 倍的分数差距
  4. final_score = relevance_score × decay_factor
  5. 按 final_score 重排，截取 top_k 返回
```

### 关键细节

| 设计点 | 实现 |
|--------|------|
| 访问历史 | 每条记忆记录最近 20 次访问时间戳 |
| 衰减范围 | 0.3× ~ 1.5×，不会归零（老记忆仍可被召回） |
| 阈值过滤 | threshold 在 decay 之前应用，衰减后的分数可能略低于阈值，但不会被过滤掉 |
| 写入延迟 | 零影响，decay 只在 search 时计算 |
| 强化更新 | 每次 search 返回的记忆，异步更新其访问时间戳（fire-and-forget，不增加搜索延迟） |
| 冷启动 | 开启前已存在的记忆，用 `updated_at` 作为单次历史回退值 |
| 最低系数 | 0.3× — 老记忆仍会返回，只是排在后面 |

### 伪代码

```python
def search_with_decay(query, threshold, top_k):
    # 1. 正常检索，扩大候选池（避免衰减后截断过早）
    candidates = vector_search(query, limit=top_k * 4)

    # 2. 阈值过滤（在 decay 之前）
    candidates = [c for c in candidates if c.score >= threshold]

    # 3. 对每条记忆计算 decay factor
    for mem in candidates:
        last_access = get_last_access_time(mem.id)  # 最近一次被搜索命中的时间
        days_idle = (now - last_access).days
        mem.decay_factor = compute_decay(days_idle)  # 范围 0.3 ~ 1.5
        mem.final_score = mem.score * mem.decay_factor

    # 4. 重排 + 截取
    candidates.sort(key=lambda x: x.final_score, reverse=True)
    return candidates[:top_k]
```

### 启用方式（Platform）

```python
from mem0 import MemoryClient
client = MemoryClient(api_key="your-api-key")
client.project.update(decay=True)
# 此后所有 search 自动带 decay
```

---

## 二、Temporal Reasoning（时间推理）

博客：https://mem0.ai/blog/introducing-temporal-reasoning-in-mem0

### 核心思想

**给每条记忆打上"时间签名"，让搜索能区分"现在"、"过去"、"将来"。**
解决的问题：用户说"我搬到深圳了"，旧记忆"住在北京"不应与新记忆同等权重。

### 写入时：两步分离

```
Step 1: Fact Extraction（不变）
  对话 → LLM 提取 → "用户住在北京"
  直接写入 vector store，add 调用立即返回

Step 2: Temporal Enrichment（新增，异步）
  对已写入的记忆 + 原始对话 + 日期 → 额外一次 LLM 调用
  提取结构化时间元数据：
  {
    "event_start": "2025-03-15",       # 事件发生时间
    "event_end": null,                  # 结束时间（null = 仍在进行）
    "time_precision": "day",            # 精度：day/week/month/year/approximate
    "memory_type": "state",             # 记忆类型（见下表）
    "state_key": "user_location",       # 状态标识（同一事实的演变链）
    "is_current": true                  # 是否为当前状态
  }
  写回 payload，patch 到已有记忆记录上
```

### 7 种记忆类型

| 类型 | 含义 | 例子 |
|------|------|------|
| `event` | 一次性事件 | "去了趟东京" |
| `state` | 持续状态 | "住在深圳" |
| `plan` | 未来计划 | "下周要出差" |
| `preference` | 偏好 | "喜欢素食" |
| `relationship` | 人际关系 | "和 Alice 结婚了" |
| `absence` | 缺席/不再有 | "戒烟了" |
| `fact` | 时间无关事实 | "Python 是编程语言" |

### 4 种时间结构

| 结构 | 含义 | 例子 |
|------|------|------|
| `event_start` | 事件开始时间 | "2025-03-15" |
| `event_end` | 事件结束时间（null=进行中） | "2025-06-01" 或 null |
| `time_precision` | 时间精度 | day / week / month / year / approximate |
| `memory_type` | 记忆类型 | event / state / plan / ... |

### State Key（状态链）— 最关键的设计

同一类事实的演变被 `state_key` 串联起来：

```
state_key="user_location":
  记忆A: "住在北京"   event_start=2024  event_end=2025-03  is_current=false  ← 被覆盖
  记忆B: "搬到深圳"   event_start=2025-03  event_end=null  is_current=true   ← 当前状态

当新记忆写入且 state_key 相同时：
  旧记忆的 event_end 自动被设置为新记忆的 event_start
  旧记忆的 is_current 变为 false
  → 不删除，只标记为历史
```

### 搜索时：意图分类 + 重排序

```
查询: "用户现在住在哪里？"

Step 1: 时间意图分类（零 LLM 调用，规则匹配）
  → 识别为 current_state 意图
  → 识别涉及 "location" 语义

Step 2: 正常向量搜索（不预过滤，与无 temporal 时完全一样）
  → 候选集: ["住在北京", "搬到深圳", "喜欢深圳美食", ...]

Step 3: Temporal Reranking（加分，不是过滤）
  对每条候选计算时间匹配分：
  - "搬到深圳": is_current=true, state_key=location → 高分加成
  - "住在北京": is_current=false, 有 event_end → 低分/扣分
  - "喜欢深圳美食": 非 location state → 中性

  final_score = semantic_score × temporal_boost

Step 4: 重排返回
  → "搬到深圳" 排在最前
```

### 7 种时间查询模式（零 LLM 调用，规则匹配）

| 模式 | 例子 | 匹配逻辑 |
|------|------|----------|
| `current_state` | "现在住哪？" | 优先 is_current=true |
| `historical_range` | "三月发生了什么？" | 匹配 event_start 在三月 |
| `duration_state` | "这份工作做了多久？" | 计算 event_start 到现在的跨度 |
| `upcoming` | "这周有什么计划？" | 匹配 plan 类型 + 未来日期 |
| `soft_recency` | "最近在忙什么？" | 偏好近期 event |
| `temporal_comparison` | "之前住哪？" | 明确要历史状态 |
| `general` | 无时间意图 | 不加分也不扣分 |

意图分类大概率基于关键词规则匹配：

```python
TEMPORAL_PATTERNS = {
    "current_state": ["now", "currently", "right now", "现在", "目前"],
    "upcoming": ["this week", "planning", "下周", "计划"],
    "historical_range": ["last month", "in March", "去年", "三月"],
    ...
}
```

### 关键设计原则

- **不预过滤**：时间意图不影响候选池，只影响排序。避免因日期缺失或精度低而丢失好结果
- **纯加分信号**：语义相关性始终主导。时间匹配但语义差的记忆不会排到前面
- **异步富化**：写入可立即返回，temporal metadata 后台 patch。搜索对未富化的记忆降级为普通排序
- **低精度降权**：`time_precision=approximate` 的记忆在时间匹配中贡献更少权重

---

## 三、两者的关系

```
                    写入时                    搜索时
                    ─────                    ─────
Temporal Reasoning  → 给记忆打时间元数据       → 根据查询意图重排序（state_key 关联）
Memory Decay        → 无操作                  → 根据访问频率重排序（access_timestamp）

叠加使用时：
final_score = semantic_score × temporal_boost × decay_factor
```

核心设计原则一致：**不删除、不预过滤、纯加分、语义相关性始终主导。**

---

## 四、在 OSS 中自实现的思路

如果要在自托管版本中实现类似效果，可以在 `score_and_rank()` 中加入两个因子：

```python
# mem0/utils/scoring.py 中扩展
def score_and_rank(semantic_results, bm25_scores, entity_boosts,
                   threshold, top_k, explain=False):
    for result in semantic_results:
        semantic_score = result.get("score") or 0.0
        if semantic_score < threshold:
            continue

        # === 新增：decay factor ===
        last_access = result["payload"].get("last_accessed_at")
        if last_access:
            days_idle = (now - parse(last_access)).days
            decay_factor = max(0.3, 1.5 - 0.6 * math.log1p(days_idle / 7))
        else:
            decay_factor = 1.0  # 无历史 → 不加不减

        # === 新增：temporal boost ===
        is_current = result["payload"].get("is_current")
        if query_intent == "current_state" and is_current:
            temporal_boost = 1.3
        elif query_intent == "current_state" and is_current is False:
            temporal_boost = 0.5
        else:
            temporal_boost = 1.0

        # 综合得分
        raw_combined = (semantic_score + bm25_score + entity_boost)
        combined = (raw_combined / max_possible) * decay_factor * temporal_boost
```

所需 payload 字段扩展：
- `last_accessed_at`：搜索命中时异步更新
- `event_start` / `event_end`：写入时由 LLM 提取
- `is_current`：由 state_key 链自动维护
- `memory_type`：写入时分类
