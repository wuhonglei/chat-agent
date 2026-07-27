# Mem0 v1.x 记忆更新逻辑分析

> 基于 Mem0 Python SDK v1.0.11（tag: v1.0.11, commit: 144627c4）

## 概述

v1.x 的记忆写入采用 **两次 LLM 调用** 架构：

1. **Fact Extraction** — 从对话中提取事实片段
2. **Memory Update Decision** — 将新事实与已有记忆对比，决策 ADD / UPDATE / DELETE / NONE

## 入口

```
POST /memories  (server/main.py:348)
  → Memory.add()  (mem0/memory/main.py:370)
    → _add_to_vector_store()  (main.py:475)
    → _add_to_graph()         (main.py:708, 并行执行，可选)
```

## 完整流程

### 路径 A — infer=False（直接存储）

逐条消息做 embedding → 直接写入 vector store，event=ADD，不做任何去重或合并。

### 路径 B — infer=True（默认，两次 LLM 调用）

```
┌─────────────────────────────────────────────────────────┐
│  第一次 LLM 调用：Fact Extraction                        │
│                                                         │
│  输入: 解析后的对话消息                                   │
│  Prompt: USER_MEMORY_EXTRACTION_PROMPT                  │
│          或 AGENT_MEMORY_EXTRACTION_PROMPT               │
│  输出: {"facts": ["fact1", "fact2", ...]}               │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│  对每条 fact 做 embedding → 搜索 top_k=5 已有记忆        │
│  汇总去重后得到 retrieved_old_memory                     │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│  第二次 LLM 调用：Memory Update Decision                 │
│                                                         │
│  输入: retrieved_old_memory + new_retrieved_facts        │
│  Prompt: DEFAULT_UPDATE_MEMORY_PROMPT                   │
│  输出: {"memory": [                                      │
│          {"id": "0", "text": "...", "event": "ADD"},    │
│          {"id": "1", "text": "...", "event": "UPDATE"}, │
│          {"id": "2", "text": "...", "event": "DELETE"}, │
│          {"id": "3", "text": "...", "event": "NONE"}    │
│        ]}                                               │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│  执行阶段（按 event 分发）                                │
│                                                         │
│  ADD    → _create_memory()    写入新记忆                  │
│  UPDATE → _update_memory()    覆盖已有记忆（同 ID，新文本）│
│  DELETE → _delete_memory()    删除已有记忆                │
│  NONE   → 无操作（或仅更新 session IDs）                  │
└─────────────────────────────────────────────────────────┘
```

## Prompt 详解

### 第一次调用：Fact Extraction

有两套 prompt，根据场景选择：

**USER_MEMORY_EXTRACTION_PROMPT**（默认）

- 只从 **user 消息**提取事实，忽略 assistant/system 消息
- 提取范围（7 类）：
  1. 个人偏好（喜欢/不喜欢）
  2. 重要个人信息（姓名、关系、日期）
  3. 计划和意图
  4. 活动/服务偏好
  5. 健康/养生偏好
  6. 职业信息
  7. 其他杂项（电影、书籍、品牌等）
- few-shot 示例内嵌在 prompt 中

```
User: Hi, my name is John. I am a software engineer.
→ {"facts": ["Name is John", "Is a Software engineer"]}

User: My favourite movies are Inception and Interstellar.
→ {"facts": ["Favourite movies are Inception and Interstellar"]}
```

**AGENT_MEMORY_EXTRACTION_PROMPT**

- 只从 **assistant 消息**提取事实，忽略 user/system �消息
- 提取 agent 的偏好、能力、性格特征、知识领域等

选择逻辑（main.py:521）：

```python
is_agent_memory = self._should_use_agent_memory_extraction(messages, metadata)
system_prompt, user_prompt = get_fact_retrieval_messages(parsed_messages, is_agent_memory)
```

### 第二次调用：Memory Update Decision

**DEFAULT_UPDATE_MEMORY_PROMPT**

核心指令：

> You are a smart memory manager which controls the memory of a system.
> You can perform four operations: (1) add into the memory, (2) update the memory,
> (3) delete from the memory, and (4) no change.

决策规则：

| 操作 | 条件 | 示例 |
|------|------|------|
| **ADD** | 新事实不在已有记忆中 | 已有: ["软件工程师"]，新事实: ["名字是 John"] → ADD |
| **UPDATE** | 新事实与已有记忆语义重叠但信息不同 | 已有: ["喜欢芝士披萨"]，新事实: ["喜欢鸡肉披萨"] → 合并为 ["喜欢芝士和鸡肉披萨"] |
| **DELETE** | 新事实与已有记忆矛盾 | 已有: ["住在北京"]，新事实: ["已搬到深圳"] → DELETE 旧记忆 |
| **NONE** | 新事实与已有记忆相同或无关 | 已有: ["喜欢芝士披萨"]，新事实: ["喜欢芝士披萨"] → NONE |

### Prompt 完整拼接示例

假设已有 2 条记忆，新提取 3 条 facts：

```
{DEFAULT_UPDATE_MEMORY_PROMPT}

Below is the current content of my memory which I have collected till now:
    [{"id": "0", "text": "User is a software engineer living in Beijing"},
     {"id": "1", "text": "User likes cheese pizza"}]

The new retrieved facts are mentioned in the triple backticks:
    ["User recently moved to Shenzhen",
     "User started learning surfing",
     "User loves chicken pizza"]

You must return your response in the following JSON structure only:
    {"memory": [{"id": "...", "text": "...", "event": "ADD|UPDATE|DELETE|NONE",
                 "old_memory": "..."}, ...]}
```

LLM 期望返回：

```json
{
  "memory": [
    {
      "id": "0",
      "text": "User is a software engineer who recently moved from Beijing to Shenzhen",
      "event": "UPDATE",
      "old_memory": "User is a software engineer living in Beijing"
    },
    {
      "id": "1",
      "text": "User loves cheese and chicken pizza",
      "event": "UPDATE",
      "old_memory": "User likes cheese pizza"
    },
    {
      "id": "2",
      "text": "User started learning surfing",
      "event": "ADD"
    }
  ]
}
```

## JSON 解析容错策略

两次 LLM 调用的解析逻辑相同，采用三层降级：

```
json.loads(remove_code_blocks(response))  →  json.loads(extract_json(response))  →  空兜底
```

辅助函数：

- `remove_code_blocks()` — 正则去掉 ```json ... ``` 包裹，去掉  标签
- `extract_json()` — 先找代码块，找不到则取第一个 `{` 到最后一个 `}` 之间的内容
- `normalize_facts()` — 兼容小模型返回 `{"fact": "..."}` 或 `{"text": "..."}` 而非纯字符串

约束方式：`response_format={"type": "json_object"}`（只保证输出是合法 JSON，不约束字段结构）。

## UUID 反幻觉机制

LLM 返回的 id 是临时整数（"0", "1", "2"...），代码中维护一个 `temp_uuid_mapping`：

```python
# 构建映射
temp_uuid_mapping = {}
for idx, item in enumerate(retrieved_old_memory):
    temp_uuid_mapping[str(idx)] = item["id"]   # "0" → 真实 UUID
    retrieved_old_memory[idx]["id"] = str(idx)

# 执行时映射回真实 UUID
self._update_memory(
    memory_id=temp_uuid_mapping[resp.get("id")],  # "0" → 真实 UUID
    data=action_text,
    ...
)
```

防止 LLM 幻觉出不存在的 UUID。

## 并行执行：Vector Store + Graph

main.py:458-465 中，vector store 和 graph 操作并行执行：

```python
with concurrent.futures.ThreadPoolExecutor() as executor:
    future1 = executor.submit(self._add_to_vector_store, ...)
    future2 = executor.submit(self._add_to_graph, ...)
    concurrent.futures.wait([future1, future2])
```

Graph 记忆（可选）独立于 vector store，存储实体关系三元组。

## 已知缺点

| 缺点 | 说明 |
|------|------|
| 延迟翻倍 | 两次 LLM 调用串行执行，延迟为两者之和 |
| 成本翻倍 | 每次写记忆消耗 2 次 LLM token |
| 第二次输入膨胀 | 每条 fact 搜索 top_k=5，汇总后可能很大 |
| LLM 决策不稳定 | UPDATE 改写易幻觉，DELETE 可能误删，无 JSON Schema 约束 |
| 搜索碎片化 | 每条 fact 独立搜索，无法整体语义匹配 |
| 无记忆关联 | 不支持"这条新记忆与那条已有记忆有关联" |
| UPDATE 覆盖丢失旧语义 | embedding 是新文本的，旧语义在检索层面丢失 |

## 相关文件

| 文件 | 作用 |
|------|------|
| `mem0/memory/main.py:370-706` | Memory.add() + _add_to_vector_store() |
| `mem0/memory/utils.py:15-28` | get_fact_retrieval_messages() |
| `mem0/memory/utils.py:84-106` | normalize_facts() |
| `mem0/memory/utils.py:109-142` | remove_code_blocks() + extract_json() |
| `mem0/configs/prompts.py:62-120` | USER_MEMORY_EXTRACTION_PROMPT |
| `mem0/configs/prompts.py:122-173` | AGENT_MEMORY_EXTRACTION_PROMPT |
| `mem0/configs/prompts.py:175-403` | DEFAULT_UPDATE_MEMORY_PROMPT |
| `mem0/configs/prompts.py:405-459` | get_update_memory_messages() |
