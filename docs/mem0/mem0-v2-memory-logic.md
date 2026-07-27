# Mem0 v2 记忆创建与检索逻辑分析

> 基于 Mem0 Python SDK v2.0.14（commit: b357a5a1）

## 概述

v2 的记忆系统采用 **单次 LLM 调用 + ADD-only** 架构：

- 写入：从对话中提取记忆，只做 ADD 操作（无 UPDATE / DELETE），通过 hash 去重 + 实体链接维护记忆关系
- 检索：语义搜索（向量）+ 关键词搜索（BM25）+ 实体 Boost，三路融合打分

---

# 第一部分：记忆创建

## 入口

```
POST /memories  (server/main.py:348)
  → Memory.add()  (mem0/memory/main.py:735)
    → _add_to_vector_store()  (main.py:849)
```

## add() 参数

```python
def add(
    messages,                          # 对话消息列表
    *,
    user_id=None,                      # 用户 ID（作用域隔离）
    agent_id=None,                     # Agent ID（作用域隔离）
    run_id=None,                       # 会话 ID（作用域隔离）
    metadata=None,                     # 自定义元数据
    timestamp=None,                    # 平台专用，OSS 不支持
    expiration_date=None,              # 过期日期 YYYY-MM-DD
    infer=True,                        # True=LLM 提取, False=直接存储
    memory_type=None,                  # "procedural_memory" 或 None
    prompt=None,                       # 自定义 prompt
)
```

## 两种路径

### 路径 A — infer=False（直接存储）

逐条消息做 embedding → 直接写入 vector store，event=ADD，不做去重或合并。

```python
for message_dict in messages:
    if message_dict["role"] == "system":
        continue
    msg_embeddings = embedding_model.embed(msg_content, "add")
    mem_id = _create_memory(msg_content, {msg_content: msg_embeddings}, metadata)
    returned_memories.append({"id": mem_id, "memory": msg_content, "event": "ADD"})
```

### 路径 B — infer=True（默认，V3 Phased Batch Pipeline）

```
┌─────────────────────────────────────────────────────────────┐
│  Phase 0: 上下文收集                                          │
│  Phase 1: 检索已有记忆（向量搜索 top_k=10）                     │
│  Phase 2: LLM 提取（单次调用，ADD-only）                       │
│  Phase 3: 批量 embedding                                      │
│  Phase 4+5: Hash 去重                                         │
│  Phase 6: 批量写入 vector store                                │
│  Phase 7: 批量实体链接                                         │
│  Phase 8: 保存消息 + 返回                                      │
└─────────────────────────────────────────────────────────────┘
```

---

### Phase 0 — 上下文收集

```python
session_scope = _build_session_scope(filters)        # 如 "user_123"
last_messages = db.get_last_messages(session_scope, limit=10)  # SQLite 历史
parsed_messages = parse_messages(messages)            # 拼接为文本
```

输出示例：
```
parsed_messages = "user: 我刚搬到深圳，之前在北京做了5年产品经理。最近开始学冲浪。
                   assistant: 深圳大梅沙确实是冲浪好去处！建议你报个入门班。"
```

### Phase 1 — 检索已有记忆

```python
query_embedding = embedding_model.embed(parsed_messages, "search")
existing_results = vector_store.search(
    query=parsed_messages,
    vectors=query_embedding,
    top_k=10,
    filters={"user_id": "user_123"},
)

# UUID → 整数映射（防 LLM 幻觉出假 UUID）
uuid_mapping = {"0": "uuid-aaa", "1": "uuid-bbb"}
existing_memories = [
    {"id": "0", "text": "User is a software engineer"},
    {"id": "1", "text": "User likes cheese pizza"},
]
```

### Phase 2 — LLM 提取（单次调用）

**System Prompt:** `ADDITIVE_EXTRACTION_PROMPT`

核心指令：
> You are a Memory Extractor — a precise, evidence-bound processor responsible for extracting rich, contextual memories from conversations. Your sole operation is ADD.

> You extract from BOTH user and assistant messages. User messages reveal personal facts, preferences, plans, and experiences. Assistant messages contain recommendations, plans, suggestions, and actionable information.

如果 `agent_id` 存在且 `user_id` 为空，追加 `AGENT_CONTEXT_SUFFIX`。

**User Prompt:** `generate_additive_extraction_prompt()` 拼接以下 sections：

```
## Summary              （用户画像摘要，可为空）
## Last k Messages      （最近 10 条历史消息）
## Recently Extracted Memories  （本次会话已提取的记忆，可为空）
## Existing Memories    （Phase 1 检索到的已有记忆，含整数 ID）
## New Messages         （当前输入的对话消息）
## Observation Date     （对话发生日期）
## Current Date         （当前系统日期）
## Custom Instructions  （用户自定义指令，可选）
```

**LLM 输出：**

```json
{
  "memory": [
    {
      "text": "User recently relocated to Shenzhen after working as a product manager in Beijing for 5 years",
      "attributed_to": "User"
    },
    {
      "text": "User recently started learning surfing and went to Dameisha beach on the weekend of July 2026",
      "attributed_to": "User"
    },
    {
      "text": "User was recommended RECOMM Surf Club for beginner surfing classes",
      "linked_memory_ids": ["0"],
      "attributed_to": "Assistant"
    }
  ]
}
```

注意：`linked_memory_ids` 中的 ID 是 Phase 1 映射的整数 ID，后续通过 `uuid_mapping` 映射回真实 UUID。

### Phase 3 — 批量 embedding

```python
mem_texts = [m.get("text", "") for m in extracted_memories]
embed_map = embedding_model.embed_batch(mem_texts, "add")
# 失败时逐条 embed 兜底
```

### Phase 4+5 — Hash 去重

```python
existing_hashes = {mem.payload["hash"] for mem in existing_results}  # 已有记忆的 MD5
seen_hashes = set()  # 当前批次内去重

for mem in extracted_memories:
    mem_hash = hashlib.md5(text.encode()).hexdigest()
    if mem_hash in existing_hashes or mem_hash in seen_hashes:
        continue  # 跳过重复
    seen_hashes.add(mem_hash)
    # 构建 payload: data, text_lemmatized, hash, created_at, updated_at, attributed_to
```

注意：去重是 **精确文本匹配**（MD5），语义相似但措辞不同的记忆不会被去重。

### Phase 6 — 批量写入 vector store

```python
vector_store.insert(vectors=all_vectors, ids=all_ids, payloads=all_payloads)
db.batch_add_history(history_records)  # 记录 ADD 事件到 history 表
```

### Phase 7 — 批量实体链接

```python
# 7a: 从所有新记忆中提取实体
all_entities = extract_entities_batch(all_texts)
# → [[("LOCATION", "Shenzhen"), ("LOCATION", "Beijing")],
#    [("ACTIVITY", "surfing"), ("LOCATION", "Dameisha beach")],
#    [("ORG", "RECOMM Surf Club")]]

# 7b: 全局去重，收集唯一实体
global_entities = {
    "shenzhen":    ("LOCATION", "Shenzhen",        {"uuid-new-1", "uuid-new-3"}),
    "beijing":     ("LOCATION", "Beijing",          {"uuid-new-1"}),
    "surfing":     ("ACTIVITY", "surfing",          {"uuid-new-2"}),
    ...
}

# 7c: 批量 embed 实体
entity_embeddings = embed_batch(entity_texts, "add")

# 7d: 精确匹配 + 语义搜索已有实体
exact_matches = _existing_entities_by_text(search_filters)  # O(1) 精确查找
existing_matches = entity_store.search_batch(...)            # 语义搜索 threshold >= 0.95

# 7e: 匹配到 → 更新 linked_memory_ids；未匹配 → 批量插入新实体
```

### Phase 8 — 保存消息 + 返回

```python
db.save_messages(messages, session_scope)  # 供下次 Phase 0 的 last_messages 使用
return [{"id": "...", "memory": "...", "event": "ADD"}, ...]
```

---

## LLM Prompt 质量规则摘要

`ADDITIVE_EXTRACTION_PROMPT` 中的关键规则：

| 规则 | 说明 |
|------|------|
| 双向提取 | 从 user 和 assistant 消息都提取 |
| 上下文丰富 | "User has a dog named Poppy" 而非 "User has a dog" |
| 时间锚定 | 相对时间转绝对时间（"last week" → "week of May 15, 2023"） |
| 数值精确 | "416 pages" 保持 "416 pages"，不概括为 "about 400" |
| 专有名词保留 | 书名、地名、品牌名必须保留原文 |
| 变迁捕获 | 捕获变化关系："switched from A to B after C" |
| 自包含 | 替换所有代词为具体名称或 "User" |
| 去重 | 与 Existing Memories 对比，语义等价则跳过 |
| 关联 | 与已有记忆相关的用 linked_memory_ids 标注 |

---

## JSON 解析容错策略

```python
json.loads(remove_code_blocks(response))  →  json.loads(extract_json(response))  →  空兜底
```

- `remove_code_blocks()`: 正则去掉 ```json...``` 包裹 +  标签
- `extract_json()`: 先找代码块，找不到则取第一个 `{` 到最后一个 `}`
- 约束方式: `response_format={"type": "json_object"}`（只保证合法 JSON，不约束字段结构）

## 错误处理（v2.0.14 改进）

```python
# v2.0.2: LLM 失败静默返回空
except Exception as e:
    logger.error(f"LLM extraction failed: {e}")
    return []

# v2.0.14: 抛出 LLMError，让调用方实现重试/降级
except Exception as e:
    raise LLMError(f"LLM extraction failed: {e}") from e
```

---

# 第二部分：记忆检索

## 入口

```
POST /search  →  Memory.search()  (main.py:1349)
  → _search_vector_store()  (main.py:1598)
```

## search() 参数

```python
def search(
    query,                   # 搜索查询
    *,
    top_k=20,                # 最大返回数
    filters=None,            # 作用域过滤（必须含 user_id/agent_id/run_id 之一）
    threshold=0.1,           # 最低语义分数
    rerank=False,            # 是否启用 reranker
    explain=False,           # 是否返回 score_details
    show_expired=False,      # 是否包含过期记忆
)
```

filters 支持高级操作符：
```python
# 精确匹配
{"user_id": "u1"}
# 比较操作符
{"key": {"gt": 10}}, {"key": {"in": ["val1", "val2"]}}
# 逻辑操作符
{"AND": [filter1, filter2]}, {"OR": [filter1, filter2]}, {"NOT": [filter1]}
```

## 完整检索流程

```
┌─────────────────────────────────────────────────────────────┐
│  Step 1: 参数校验 + 预处理                                    │
│  Step 2: 预处理 query（词形还原 + 实体提取）                    │
│  Step 3: 语义搜索（向量检索，过度召回 top_k*4 或 60）            │
│  Step 4: 关键词搜索（BM25，如果 vector store 支持）             │
│  Step 5: BM25 分数归一化                                      │
│  Step 6: 实体 Boost 计算                                      │
│  Step 7: 过滤过期记忆 + 构建候选集                              │
│  Step 8: 三路融合打分 + 排名                                    │
│  Step 9: 格式化返回                                            │
└─────────────────────────────────────────────────────────────┘
```

---

### Step 1 — 参数校验 + 预处理

```python
_validate_search_params(threshold=threshold, top_k=top_k)
query = _validate_and_trim_search_query(query)
# 验证 filters 必须含 user_id/agent_id/run_id
# 处理高级过滤操作符（AND/OR/NOT/in/nin/contains/icontains）
```

### Step 2 — 预处理 query

```python
query_lemmatized = lemmatize_for_bm25("深圳冲浪")
# → "深圳 冲浪"（spaCy 词形还原：去停用词、标点，动词→原形，-ing 保留原词）

query_entities = extract_entities("深圳冲浪")
# → [("LOCATION", "深圳")]
```

**lemmatize_for_bm25 处理逻辑：**
1. 转小写
2. spaCy 分词 + 词形还原
3. 过滤标点和停用词（to, as, a, in, for...）
4. 保留词元，-ing 结尾的额外保留原词（解决 meeting/meet 歧义）
5. 中文基本原样返回（无词形变化）

**extract_entities 五种提取策略：**

| 策略 | priority | confidence | 示例 |
|------|----------|-----------|------|
| spaCy NER | 0 | 0.95 | "Shenzhen"→GPE, "RECOMM Surf Club"→ORG |
| 技术标识符 | 1 | 0.9 | "mem0.memory.main" |
| 大写序列 | 2 | 0.8 | "Ocean Park", "University of Hong Kong" |
| 引号文本 | 3 | 0.75 | "A Court of Thorns and Roses" |
| 名词短语 | 4 | 0.45 | "product manager", "machine learning" |

冲突解决：span 重叠时，priority 数值小的优先保留。

### Step 3 — 语义搜索（向量检索）

```python
embeddings = embedding_model.embed(query, "search")
semantic_results = vector_store.search(
    query=query,
    vectors=embeddings,
    top_k=max(limit * 4, 60),   # 过度召回，供后续融合打分
    filters=filters,
)
# → [
#     {id: "uuid-1", score: 0.82, payload: {data: "User moved to Shenzhen..."}},
#     {id: "uuid-2", score: 0.71, payload: {data: "User started surfing..."}},
#     {id: "uuid-3", score: 0.45, payload: {data: "User likes cheese pizza"}},
#   ]
```

### Step 4 — 关键词搜索（BM25）

```python
keyword_results = vector_store.keyword_search(
    query=query_lemmatized,     # 使用词形还原后的版本
    top_k=max(limit * 4, 60),
    filters=filters,
)
# → [
#     {id: "uuid-1", score: 12.5},   # "深圳" 精确命中
#     {id: "uuid-2", score: 8.3},    # "冲浪" 精确命中
#   ]
```

并非所有 vector store 都支持 `keyword_search`，不支持时 `keyword_results=None`，跳过 BM25。

### Step 5 — BM25 分数归一化

```python
# 根据 query 长度自适应选择 sigmoid 参数
midpoint, steepness = get_bm25_params(query, lemmatized=query_lemmatized)
```

参数选择：

| query 词数 | midpoint | steepness |
|-----------|----------|-----------|
| ≤ 3 | 5.0 | 0.7 |
| ≤ 6 | 7.0 | 0.6 |
| ≤ 9 | 9.0 | 0.5 |
| ≤ 15 | 10.0 | 0.5 |
| > 15 | 12.0 | 0.5 |

归一化公式：
```python
normalize_bm25(raw_score, midpoint, steepness)
# = 1.0 / (1.0 + exp(-steepness * (raw_score - midpoint)))
# → 映射到 [0, 1]
```

### Step 6 — 实体 Boost 计算

```python
query_entities = [("LOCATION", "深圳")]

# 1. 去重 + 限制最多 8 个实体
# 2. 批量 embed 实体文本
# 3. 对每个实体并发搜索 entity_store（ThreadPoolExecutor, max_workers=4）
entity_store.search(query="深圳", vectors=embedding, top_k=500, filters=filters)

# 4. 对搜索结果计算 boost
for match in matches:
    if match.score < 0.5:        # 相似度阈值
        continue
    linked_memory_ids = match.payload["linked_memory_ids"]
    num_linked = len(linked_memory_ids)

    # 关联记忆越多，单条 boost 越小（反稀释）
    memory_count_weight = 1.0 / (1.0 + 0.001 * ((num_linked - 1) ** 2))
    boost = similarity * ENTITY_BOOST_WEIGHT(0.5) * memory_count_weight

    # 取最大值（不累加，防止单条记忆因多实体命中获得过高加分）
    for memory_id in linked_memory_ids:
        memory_boosts[memory_id] = max(memory_boosts.get(memory_id, 0.0), boost)
```

示例：
```
查询: "深圳冲浪"
entity: ("LOCATION", "深圳") → entity_store 搜索 → 匹配到 linked_memory_ids=["uuid-1", "uuid-3"]
  → memory_boosts = {"uuid-1": 0.46, "uuid-3": 0.46}
```

### Step 7 — 过滤过期记忆 + 构建候选集

```python
for mem in semantic_results:
    if not show_expired and _payload_is_expired(mem.payload):
        continue  # 过期记忆默认隐藏
    if not mem.payload.get("data"):
        continue  # 无内容的空记忆
    candidates.append({"id": mem.id, "score": mem.score, "payload": mem.payload})
```

### Step 8 — 三路融合打分 + 排名

```python
score_and_rank(
    semantic_results=candidates,
    bm25_scores=bm25_scores,        # {"uuid-1": 0.996, "uuid-2": 0.900}
    entity_boosts=entity_boosts,    # {"uuid-1": 0.46, "uuid-3": 0.46}
    threshold=0.1,
    top_k=5,
)
```

**打分公式：**

```
combined = (semantic + bm25 + entity_boost) / max_possible

其中：
  semantic      ∈ [0, 1]    向量余弦相似度（原始值，未加权）
  bm25          ∈ [0, 1]    sigmoid 归一化后的关键词匹配分
  entity_boost  ∈ [0, 0.5]  实体链接加分
  max_possible  = 1.0 + (有BM25?1.0:0) + (有entity?0.5:0)
```

三路信号的"权重"取决于 max_possible 的稀释效果：

| 场景 | max_possible | semantic 贡献占比 |
|------|-------------|------------------|
| 仅 semantic | 1.0 | 100% |
| semantic + BM25 | 2.0 | 50% |
| semantic + BM25 + entity | 2.5 | 40% |

**重要：** semantic < threshold 的候选直接丢弃，不参与后续打分。即使 BM25 和 entity_boost 很高也无法挽救。

**打分示例：**

```
uuid-1: semantic=0.82, bm25=0.996, entity=0.46  → (0.82+0.996+0.46)/2.5 = 0.910
uuid-2: semantic=0.71, bm25=0.900, entity=0.0   → (0.71+0.900+0.0)/2.5  = 0.644
uuid-3: semantic=0.45, bm25=0.0,   entity=0.46  → (0.45+0.0+0.46)/2.5   = 0.364
```

按 combined score 降序排列，取 top_k，过滤 threshold < 0.1 的结果。

### Step 9 — 格式化返回

```python
{
    "results": [
        {
            "id": "uuid-1",
            "memory": "User recently relocated to Shenzhen...",
            "score": 0.910,
            "user_id": "user_123",
            "created_at": "2026-07-27T10:30:00Z",
            "updated_at": "2026-07-27T10:30:00Z",
        },
        ...
    ]
}
```

当 `explain=True` 时，每条结果额外包含：
```json
{
    "score_details": {
        "semantic_score": 0.82,
        "bm25_score": 0.996,
        "entity_boost": 0.46,
        "raw_score": 2.276,
        "max_possible_score": 2.5,
        "final_score": 0.910,
        "threshold": 0.1
    }
}
```

---

# 第三部分：v1.x → v2 架构对比

| 维度 | v1.x | v2 (v2.0.14) |
|------|------|-------------|
| LLM 调用次数 | 2 次（提取 + 决策） | 1 次（合并提取+决策） |
| 操作类型 | ADD / UPDATE / DELETE / NONE | 仅 ADD |
| 已有记忆检索 | 每条 fact 单独搜索 top_k=5 | 整体消息搜索 top_k=10 |
| 去重方式 | LLM 判断语义去重 | MD5 hash 精确去重 |
| 记忆关联 | 无 | linked_memory_ids |
| 实体链接 | 无 | Phase 7 自动提取 + 链接 |
| 检索方式 | 纯向量搜索 | 向量 + BM25 + entity boost 三路融合 |
| 检索打分 | 单一 cosine score | (semantic + bm25 + entity) / max_possible |
| Graph 支持 | 并行执行 _add_to_graph() | 已移除 |
| 错误处理 | LLM 失败静默返回空 | 抛出 LLMError |
| 过期记忆 | 无 | expiration_date 支持 |

---

# 第四部分：相关源码文件索引

| 文件 | 作用 |
|------|------|
| `mem0/memory/main.py:735-848` | Memory.add() |
| `mem0/memory/main.py:849-1176` | _add_to_vector_store() 完整 pipeline |
| `mem0/memory/main.py:558-578` | _normalize_entity_text(), _existing_entities_by_text() |
| `mem0/memory/main.py:1349-1492` | Memory.search() |
| `mem0/memory/main.py:1598-1701` | _search_vector_store() 混合检索 |
| `mem0/memory/main.py:1703-1783` | _compute_entity_boosts() |
| `mem0/configs/prompts.py:468-945` | ADDITIVE_EXTRACTION_PROMPT |
| `mem0/configs/prompts.py:947-1014` | AGENT_CONTEXT_SUFFIX |
| `mem0/configs/prompts.py:1016-1062` | generate_additive_extraction_prompt() |
| `mem0/utils/scoring.py:16-40` | get_bm25_params() |
| `mem0/utils/scoring.py:43-54` | normalize_bm25() |
| `mem0/utils/scoring.py:60-139` | score_and_rank() |
| `mem0/utils/lemmatization.py:22-50` | lemmatize_for_bm25() |
| `mem0/utils/entity_extraction.py:751-758` | extract_entities() |
| `mem0/utils/entity_extraction.py:731-748` | _extract_entities_from_doc() 五种策略 |
| `mem0/utils/entity_extraction.py:705-728` | _resolve_candidates() 冲突解决 |
