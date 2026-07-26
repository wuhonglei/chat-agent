# 历史消息上下文压缩优化方案

> 基于六大框架（chat-agent / claude-code / opencode / codex / hermes-agent / deer-flow）源码深度分析，
> 针对 chat-agent 的使用场景设计。

## 一、现状分析 #

### 1.1 当前架构

```
用户消息到达
  → A 检查点: prepare_history_messages()           ← orchestrator 层，每请求执行一次
      ① split_history_by_rounds(max_rounds=20)     ← 按轮数硬切
      ② compress_history_messages()                 ← 工具结果压缩（summary 替换 / 截断）
      ③ truncate_in_window_by_round_tokens(25%)     ← token 预算裁剪
      ④ 窗口外摘要（LLM 调用，增量合并）
  → stream_session_events()
      → for iteration in range(max_total_iterations):
          → _build_round_prompt_messages()           ← 拼装 base + tool_rounds
          → _stream_tool_round_events()              ← LLM 调用 + 工具执行
          → _check_round_context_budget(80%)         ← 超阈值则硬停工具调用
```

相关源码文件：

| 文件 | 作用 |
|------|------|
| `backend/app/services/chat/history_context_service.py` | A 检查点：历史消息窗口压缩 |
| `backend/app/utils/history_truncate.py` | 轮数分割 + token 截断 |
| `backend/app/utils/context_compactor.py` | FAISS 语义截断（工具返回时） |
| `backend/app/services/conversation/context_summary_service.py` | 窗口外 LLM 摘要 |
| `backend/app/agents/chat_session_agent.py` | B 检查点：工具轮预算检查 |
| `backend/app/services/chat/chat_orchestrator.py` | A 检查点调用入口 |
| `backend/app/schemas/config.py` | 配置定义（L464-650） |

### 1.2 现有问题

| # | 问题 | 影响 | 对标框架 |
|---|------|------|----------|
| 1 | A/B 检查点分离，A 固定 25% 历史预算 | 短对话浪费空间，长对话历史不够用 | claude-code/codex/deer-flow 均为单一检查点 |
| 2 | 工具循环中无中间压缩 | 单轮工具返回 50K+ 时直接撑爆 context 或被迫提前停止 | codex 有 MidTurn，hermes-agent 有 pre-API |
| 3 | 80% 硬停工具调用，不做压缩 | 过早终止工具循环，丢失后续工具调用机会 | 其他框架均先压缩再决定是否停止 |
| 4 | 摘要无结构化模板 | 100+ 轮后摘要质量退化 | claude-code 9 段模板，opencode 5 段模板 |
| 5 | 无反抖动保护 | 高频对话每轮都触发 LLM 摘要 | hermes-agent 双计数器 + 300s 恢复 |
| 6 | 摘要失败静默降级 | 用户无感知，后续请求反复重试 | hermes-agent 有 fallback + warning |
| 7 | 摘要未压缩 | prior_summary 持续膨胀，占满 LLM 输入 | hermes-agent 有"摘要的摘要"迭代压缩 |
| 8 | 并发请求竞态 | 两个请求同时滑动窗口，摘要重复生成 | codex 用 mutex 保护 |

### 1.3 当前配置默认值

```yaml
# history_window
max_rounds: 20
token_ratio: 0.25                    # 历史消息 token 预算 = context_limit × 25%

# tool_result_compression
threshold_tokens: 5000               # FAISS 语义截断目标
tolerance_tokens: 8000               # FAISS 语义截断门限
message_summary_threshold_tokens: 2000  # 窗口内工具消息截断阈值
tool_arg_max_chars: 500              # tool_use 参数截断门限
tool_arg_keep_chars: 200             # tool_use 参数保留字符数

# window_out_summary
enabled: true
summary_max_tokens: 1000             # 窗口外摘要最大 token

# ChatContextConfig
tool_round_context_limit_ratio: 0.8  # 工具轮 80% 硬停
```

---

## 二、框架对比 #

### 2.1 检查点架构对比

| 框架 | 检查点数量 | 检查位置 | 是否区分历史/当前轮 |
|------|-----------|----------|---------------------|
| **chat-agent** | 2 个分离 | A: 请求入口；B: 工具轮后 | ✅ 分开管理 |
| **claude-code** | 3 层统一 | 每次 API 调用前 | ❌ 统一处理 |
| **codex** | 2 个统一 | PreTurn + MidTurn | ❌ 同一阈值 |
| **opencode** | 1 个 | LLM step 完成后 | ❌ 统一处理 |
| **deer-flow** | 2 个 hook | 每次 model call 前 | ❌ 统一处理 |
| **hermes-agent** | 2 次/轮 | Preflight + Post-response | ❌ 同一阈值 |

**结论**：chat-agent 是唯一将"历史消息"和"当前轮"分开管理的框架。
其他框架均检查**总 prompt 大小**，不区分来源。

### 2.2 阈值对比（128K context 模型）

| 框架 | 阈值 | 128K 换算 | 含义 |
|------|------|-----------|------|
| **chat-agent** | 25% context | **32K** 仅历史 | 历史消息固定预算 |
| **hermes-agent** | 50% effective_window | **~60K** 总 prompt | 总 prompt 阈值 |
| **claude-code** | effective - 13K | **~107K** 总 prompt | 总 prompt 阈值 |
| **opencode** | input - min(20K, maxOut) | **~108K** 总 prompt | 总 prompt 阈值 |
| **codex** | auto_compact_limit | **~100K+** 总 prompt | 总 prompt 阈值 |
| **deer-flow** | fraction 0.8 | **~102K** 总 prompt | 总 prompt 阈值 |

**结论**：chat-agent 的 25% 是最低的。但其他框架的阈值是**总 prompt**（含 system + history + current turn），
而 chat-agent 的 25% 是**仅历史**的预算。两者不可直接比较。

### 2.3 各框架压缩策略一览

| 压缩手段 | chat-agent | claude-code | codex | opencode | hermes-agent | deer-flow |
|----------|------------|-------------|-------|----------|--------------|-----------|
| 旧工具结果清除 | ❌ | Microcompact 60min | ❌ | prune 40K | 1 行摘要 | 磁盘外部化 |
| 历史消息裁剪 | 轮数+token | Snip + AutoCompact | PreTurn 全量替换 | 全量替换 | 头尾保护+token | 消息数/fraction |
| 工具结果压缩 | FAISS 语义 | 磁盘持久化 | 中间截断 | 磁盘外部化 | 摘要替换 | 头尾截断 |
| LLM 摘要 | 增量合并 | 9 段结构化 | handoff summary | 5 段结构化+增量 | 结构化模板 | 默认关闭 |
| 摘要自压缩 | ❌ | ❌ | ❌ | ❌ | ✅ 迭代压缩 | ❌ |
| 反抖动 | ❌ | 3 次熔断 | token_budget 标志 | ❌ | 双计数器+300s | ❌ |

---

## 三、优化方案 #

### 3.1 核心改动：统一检查点

**将 A、B 两个检查点合并为单一检查点**，在每次 LLM 调用前统一检查总 prompt 大小，
按优先级分级降级处理。对齐 claude-code / codex / deer-flow 的架构。

#### 改动前

```
用户消息到达
  → A: prepare_history_messages()       ← 固定 25% 历史预算，每请求执行
  → for iteration:
      → LLM 调用 + 工具执行
      → B: _check_round_context_budget(80%)  ← 超阈值硬停
```

#### 改动后

```
用户消息到达
  → stream_session_events()
    → for iteration:
        → unified_context_guard()       ← 统一检查点，每次 LLM 调用前
            total = count(system + history + tool_rounds)
            threshold = context_limit - max_output - buffer
            if total > threshold:
                ① 压缩历史工具结果（已完成轮次的 summary 替换 / 截断）
                ② 仍超 → 生成窗口外摘要 + 截断更早历史
                ③ 仍超 → 压缩当前轮旧工具结果（保留最新 2 个）
                ④ 仍超 → 停止工具调用，进入 final answer
        → LLM 调用 + 工具执行
```

#### 阈值计算

```python
# 统一阈值（对齐 claude-code / opencode）
max_output_tokens = min(model_max_output, 8192)   # 预留输出空间
buffer_tokens = 13000                               # 安全缓冲（对齐 claude-code）
context_threshold = context_limit - max_output_tokens - buffer_tokens

# 示例（128K 模型）：
# context_threshold = 128000 - 8192 - 13000 = 106808 (~107K)
```

### 3.2 分级降级策略

`unified_context_guard` 的降级逻辑：

```
输入: base_prompt_messages, tool_round_messages, conversation_id

Step 1: 计算总 token
  total_tokens = count_messages_tokens(
      base_prompt_messages + tool_round_messages
  )
  if total_tokens <= context_threshold:
      return  # 未超阈值，不做任何处理

Step 2: 压缩历史工具结果（零成本，低破坏性）
  # 目标：所有已完成轮次（history_messages）中 assistant 消息的 ToolResultBlock
  # 不分"窗口内外" — 所有历史轮次的工具结果都是压缩目标
  # 这些结果对应的轮次已经结束，模型的 assistant 回复已提炼了关键信息
  # 用 summary 替换 content，或 head-tail 截断
  # 不动当前轮（本轮 for 循环产生的）工具结果
  for msg in history_messages:  # 所有历史轮次，不限于最近 N 轮
      for block in msg.content_blocks:
          if isinstance(block, ToolResultBlock):
              if block.summary:
                  block.content = block.summary  # 用 summary 替换
              elif count_tokens(block.content) > 2000:
                  block.content = head_tail_truncate(block.content)
  recheck: if total_tokens <= context_threshold: return

Step 3: 生成窗口外摘要（LLM 成本，中破坏性）
  # 目标：超出剩余 token 预算的更早历史消息
  # "窗口"由动态 token 预算定义（非固定轮数）：
  #   remaining_budget = context_threshold
  #                      - count(system_prompt)
  #                      - count(current_user_message)
  #                      - count(tool_round_messages)
  #   从最新轮往旧轮累加，超出 remaining_budget 的消息为"窗口外"
  # 整条消息替换为 LLM 生成的摘要，释放空间最大
  # 信息损失最大，但处理的是最旧的消息
  remaining_budget = context_threshold - count(system + user + tool_rounds)
  in_window, out_of_window = split_by_token_budget(
      history_messages, remaining_budget
  )
  if out_of_window and window_out_summary.enabled:
      summary = await summary_service.summarize_merge(
          prior_summary, out_of_window
      )
      persist_summary(conversation_id, summary)
      # 从 base_prompt_messages 中移除窗口外消息，注入摘要
  recheck: if total_tokens <= context_threshold: return

Step 4: 压缩当前轮旧工具结果（零成本，高破坏性）— 最后手段
  # 目标：本轮 for 循环中第 1~N-2 次迭代的工具结果
  # 只有在 Step 2、3 都不够时才执行
  # ⚠️ 注意：这会丢失当前轮早期工具结果中的详细信息
  #
  # Size-aware 策略（而非纯按轮次保留最新 N 个）：
  # 按工具结果大小降序排序，从最大的开始逐个压缩，
  # 一旦 total_tokens 降到阈值以下立即停止。
  # 这样保留小的但可能关键的结果（如错误码、状态标记），
  # 只压缩大的冗余结果（如大文件内容、搜索结果列表）。
  compressible = tool_round_messages[:-2]  # 保留最新 2 个（模型决定下一次调用）
  candidates = [
      (i, msg) for i, msg in enumerate(compressible)
      if len(msg.content) > 1000
  ]
  # 按大小降序，从最大的开始压缩
  candidates.sort(key=lambda x: len(x[1].content), reverse=True)
  for i, msg in candidates:
      msg.content = head_tail_truncate(msg.content, 500, 500)
      total_tokens = count_messages_tokens(
          base_prompt_messages + tool_round_messages
      )
      if total_tokens <= context_threshold:
          return  # 已达标，剩余的小结果保留完整
  recheck: if total_tokens <= context_threshold: return

Step 5: 压缩后仍超限，停止工具调用
  return STOP_TOOLS_SIGNAL
```

**降级顺序设计原则：**

```
成本递增:    零（截断）    →  LLM（摘要）    →  零（截断）    →  行为干预
破坏性递增:  低（旧轮次）  →  中（旧消息）    →  高（工作记忆） →  最高（停止）
```

- **Step 2 在 Step 4 前**：历史工具结果来自已完成的轮次，模型的 assistant 回复已提炼了关键信息，
  压缩它们不会影响当前轮的推理质量。当前轮工具结果是模型的"工作记忆"，压缩会丢失正在进行的调研内容。
- **Step 3 在 Step 4 前**：窗口外摘要是 LLM 调用有延迟，但释放空间最大（整条消息替换），
  且处理的是最旧的消息。优先执行可以避免触碰当前轮的工作记忆。
- **Step 4 是最后手段**：只有历史空间全部释放后仍不够时，才压缩当前轮旧结果。
  典型场景：单轮工具调用累积了 100K+ 结果（如连续读取大文件），历史空间不足以抵消。
  采用 **size-aware 策略**（按大小降序，从最大的开始压缩，达标即停），
  而非纯按轮次保留最新 N 个。这样保留小的但可能关键的结果（错误码、状态标记），
  只压缩大的冗余结果（大文件内容、搜索结果列表）。
  例如：10 轮调研中，工业界结果各 30K、学术界结果各 5K，优先压缩工业界的大结果，
  保留学术界的小结果；如果工业界结果小但关键、学术界结果大但冗余，则优先压缩学术界。

#### 关键定义澄清

**"历史工具结果"（Step 2 的压缩目标）：**

指所有已完成轮次（`history_messages`）中 assistant 消息的 `ToolResultBlock`，
**不分"窗口内外"**。与当前实现的区别：

| | 当前实现 | 新方案 |
|---|----------|--------|
| Step ① 压缩范围 | 窗口内（最近 20 轮） | 所有历史轮次 |
| "窗口"定义 | 固定 max_rounds=20 | 动态 token 预算 |
| "窗口外"定义 | 第 21 轮及更早 | 超出剩余预算的更早消息 |
| max_rounds 角色 | 唯一窗口定义 | 已删除 |

**"窗口外"（Step 3 的摘要目标）：**

由动态 token 预算定义，计算方式：

```
remaining_budget = context_threshold
                   - count(system_prompt)
                   - count(current_user_message)
                   - count(tool_round_messages)

从最新轮往旧轮累加 history 消息的 token，
超出 remaining_budget 的消息为"窗口外"。
```

示例（128K 模型，context_threshold=107K）：

```
Step 2 压缩后:
  system=2K, history=85K, current_user=1K, tool_rounds=20K
  total=108K > 107K → 触发 Step 3

  remaining_budget = 107K - 2K - 1K - 20K = 84K
  从最新轮往旧轮累加：
    轮次 20 (最新): 8K   → 累计 8K,  窗口内
    轮次 19: 12K         → 累计 20K, 窗口内
    轮次 18: 15K         → 累计 35K, 窗口内
    轮次 17: 10K         → 累计 45K, 窗口内
    轮次 16: 20K         → 累计 65K, 窗口内
    轮次 15: 18K         → 累计 83K, 窗口内
    轮次 14: 25K         → 累计 108K > 84K → 停止

  窗口内 = 轮次 15-20 (6 轮, 83K)
  窗口外 = 轮次 1-14 (14 轮) → Step 3 做 LLM 摘要
```

### 3.3 摘要质量改进

#### 结构化摘要模板

替换当前的自由文本 prompt（`user_prompt.py:119-148`）为结构化模板：

```
<task>
{%- if prior_summary %}
请将已有摘要与新增对话内容合并为一段结构化摘要。
{%- else %}
请根据新增对话内容生成一段结构化摘要。
{%- endif %}
</task>

<output_format>
## 用户核心需求
用户的主要目标和诉求

## 已完成工作
已解决的问题和交付的内容

## 进行中任务
当前正在处理的任务

## 待处理需求
用户提出但尚未完成的需求

## 关键决策
对话中做出的重要技术/方案决策

## 关键上下文
后续对话可能需要的背景信息（文件路径、配置、约束等）
</output_format>

<requirements>
<requirement>每个章节若无对应内容可省略，不要编造。</requirement>
<requirement>控制在 {{ max_tokens_hint }} 字以内。</requirement>
<requirement>保留具体的文件路径、命令、配置值等可操作信息。</requirement>
</requirements>

{%- if prior_summary %}
<prior_summary>{{ prior_summary }}</prior_summary>
{%- endif %}

<new_messages>{{ new_messages_text }}</new_messages>
```

#### 摘要自压缩

在 `context_summary_service.py` 的 `summarize_merge` 中增加：

```python
async def summarize_merge(self, prior_summary, messages_to_summarize, max_tokens):
    # 摘要自压缩：prior_summary 过大时先压缩
    if prior_summary:
        prior_tokens = self.token_calculator.count_tokens(prior_summary)
        if prior_tokens > max_tokens * 1.5:
            prior_summary = await self._compress_summary(
                prior_summary, max_tokens // 2
            )

    # ... 原有合并逻辑 ...
```

### 3.4 反抖动保护

在 `conversation_contexts_db.py` 中新增字段：

```python
summary_failure_count: int = Field(default=0, description="连续摘要失败次数")
last_summary_failure_at: datetime | None = Field(default=None, description="上次失败时间")
```

逻辑：

```python
FAILURE_THRESHOLD = 3
RECOVERY_SECONDS = 300

async def _generate_summary_with_guard(self, conversation_id, ...):
    ctx = self._get_context(conversation_id)

    # 反抖动检查
    if ctx and ctx.summary_failure_count >= FAILURE_THRESHOLD:
        if ctx.last_summary_failure_at:
            elapsed = (now - ctx.last_summary_failure_at).total_seconds()
            if elapsed < RECOVERY_SECONDS:
                logger.info("Summary blocked by anti-thrashing",
                            remaining=RECOVERY_SECONDS - elapsed)
                return ctx.summary_before_window  # 返回旧摘要
        # 恢复窗口已过，重置计数器
        self._reset_failure_count(conversation_id)

    try:
        summary = await summary_service.summarize_merge(...)
        self._reset_failure_count(conversation_id)
        return summary
    except Exception:
        self._increment_failure_count(conversation_id)
        return ctx.summary_before_window if ctx else None
```

### 3.5 竞态保护

使用 Redis 分布式锁（chat-agent 已有 Redis 依赖）：

```python
async def _guarded_summary_generation(self, conversation_id, ...):
    lock_key = f"summary_lock:{conversation_id}"
    if not await redis.set(lock_key, "1", nx=True, ex=30):
        logger.info("Summary generation locked by another request",
                    conversation_id=conversation_id)
        return None  # 另一个请求正在生成摘要
    try:
        return await self._generate_summary_with_guard(conversation_id, ...)
    finally:
        await redis.delete(lock_key)
```

---

## 四、配置变更 #

### 4.1 新增配置

```python
class UnifiedContextGuardConfig(BaseModel):
    """统一上下文守卫配置"""

    enabled: bool = Field(default=True, description="是否启用统一上下文守卫")

    # 阈值（替代原来的 tool_round_context_limit_ratio 和 history_window.token_ratio）
    buffer_tokens: int = Field(
        default=13000,
        description="安全缓冲 token 数（对齐 claude-code AUTOCOMPACT_BUFFER_TOKENS）",
    )
    max_output_tokens: int = Field(
        default=8192,
        description="预留输出 token 数",
    )

    # 分级降级参数
    keep_recent_tool_results: int = Field(
        default=2,
        description="当前轮压缩时保留的最新工具结果数量",
    )
    tool_result_compress_threshold_chars: int = Field(
        default=1000,
        description="当前轮工具结果超过该字符数时触发压缩",
    )

    # 反抖动
    anti_thrash_failure_threshold: int = Field(
        default=3,
        description="连续摘要失败几次后触发反抖动保护",
    )
    anti_thrash_recovery_seconds: int = Field(
        default=300,
        description="反抖动恢复窗口（秒）",
    )

    # 竞态保护
    lock_timeout_seconds: int = Field(
        default=30,
        description="摘要生成分布式锁超时（秒）",
    )
```

### 4.2 废弃配置

以下配置在统一检查点后不再需要，但保留向后兼容（新配置优先）：

```python
# 旧配置（保留但不再使用）
class HistoryWindowConfig(BaseModel):
    token_ratio: float = 0.25  # ← 被 UnifiedContextGuardConfig 替代
    max_rounds: int = 20       # ← 已删除，纯 token 预算驱动
                                 # 删除原因：其他框架（claude-code/codex/opencode）
                                 # 均无固定轮数限制，token 预算自然限制窗口大小

class ChatContextConfig(BaseModel):
    tool_round_context_limit_ratio: float = 0.8  # ← 被 UnifiedContextGuardConfig 替代
```

### 4.3 兼容性处理

```python
class ChatContextConfig(BaseModel):
    unified_guard: UnifiedContextGuardConfig = Field(
        default_factory=UnifiedContextGuardConfig,
    )

    @property
    def effective_context_threshold(self) -> int:
        """计算统一阈值，优先使用新配置，回退到旧配置。"""
        if self.unified_guard.enabled:
            # 新逻辑：由调用方传入 context_limit
            raise ValueError("Use compute_threshold(context_limit) instead")
        # 旧逻辑兼容
        ...
```

---

## 五、改动文件清单 #

### 5.1 核心改动

| 文件 | 改动类型 | 说明 |
|------|----------|------|
| `backend/app/agents/chat_session_agent.py` | **重写** | 新增 `unified_context_guard()`，删除 `_check_round_context_budget()` |
| `backend/app/services/chat/history_context_service.py` | **重构** | 拆分为独立的压缩函数，供统一守卫按需调用 |
| `backend/app/services/chat/chat_orchestrator.py` | **简化** | 删除 A 检查点调用（L354-373），历史压缩移入 agent 层 |
| `backend/app/schemas/config.py` | **新增** | `UnifiedContextGuardConfig` 配置类 |
| `backend/app/services/conversation/context_summary_service.py` | **增强** | 结构化模板 + 摘要自压缩 + 反抖动 |

### 5.2 辅助改动

| 文件 | 改动类型 | 说明 |
|------|----------|------|
| `backend/app/prompts/user_prompt.py` | **重写** | 结构化摘要模板 |
| `backend/app/models/conversation_contexts_db.py` | **新增字段** | `summary_failure_count`、`last_summary_failure_at` |
| `backend/app/utils/history_truncate.py` | **新增函数** | `split_history_by_token_budget()`（替代轮数分割） |

### 5.3 测试改动

| 文件 | 改动类型 | 说明 |
|------|----------|------|
| `backend/tests/services/chat/test_history_context_service.py` | **更新** | 适配新的压缩流程 |
| `backend/tests/agents/test_unified_context_guard.py` | **新增** | 统一守卫单元测试 |

### 5.4 数据库迁移

| 迁移文件 | 说明 |
|----------|------|
| 新增 Alembic 迁移 | `conversation_contexts` 表新增 2 个字段 |

---

## 六、实施计划 #

### Phase 1: 统一检查点（核心）

**目标**：合并 A/B 检查点，替换固定比例为总上下文阈值

**改动量**：~200 行

**步骤**：

1. 新增 `UnifiedContextGuardConfig` 配置类（`config.py`）
2. 在 `chat_session_agent.py` 中新增 `unified_context_guard()` 方法
3. 将 `history_context_service.py` 的压缩逻辑拆分为可独立调用的函数：
   - `compress_tool_round_messages()` — 当前轮工具结果压缩
   - `compress_history_tool_results()` — 历史工具结果压缩
   - `generate_window_out_summary()` — 窗口外摘要生成
4. 在 for iteration 循环中，LLM 调用前调用 `unified_context_guard()`
5. 删除 `_check_round_context_budget()` 方法
6. 简化 `chat_orchestrator.py` 中的 A 检查点调用

**验证**：`make test -- --ignore=tests/mcp_demo`

### Phase 2: 摘要质量改进

**目标**：结构化摘要模板 + 摘要自压缩

**改动量**：~100 行

**步骤**：

1. 重写 `user_prompt.py` 中的 `WINDOW_OUT_SUMMARY_MERGE_PROMPT`
2. 在 `context_summary_service.py` 中增加摘要自压缩逻辑
3. 更新 `history_context_service.py` 中摘要生成的调用方式

**验证**：手动测试长对话摘要质量

### Phase 3: 反抖动 + 竞态保护

**目标**：防止高频摘要调用和并发竞态

**改动量**：~80 行

**步骤**：

1. `conversation_contexts_db.py` 新增字段
2. 编写 Alembic 迁移
3. 在摘要生成流程中增加反抖动检查
4. 增加 Redis 分布式锁

**验证**：并发请求测试

### 总体时间估算

| Phase | 工作量 | 风险 |
|-------|--------|------|
| Phase 1 | 2-3 天 | 中（核心逻辑重构，需充分测试） |
| Phase 2 | 1 天 | 低（prompt 改动，不影响逻辑） |
| Phase 3 | 0.5 天 | 低（新增字段 + 独立逻辑） |
| **合计** | **3.5-4.5 天** | |

---

## 七、不建议做的事 #

| 方案 | 不建议原因 |
|------|-----------|
| 引入磁盘外部化 | chat-agent 是 Web 服务，模型无法主动读取磁盘；当前 FAISS 语义截断更智能 |
| 时间触发清理（microcompact） | 请求驱动架构，无长连接；用户离开 = 自然终止 |
| Prompt cache 保护 | 当前用 OpenAI 兼容 API，prompt caching 机制不同 |
| 全量替换历史 | 增量摘要合并已实现，全量替换会丢失累积上下文 |
| 分离 compaction agent | 增加架构复杂度，chat-agent 的摘要场景相对简单 |

---

## 八、预期收益 #

| 指标 | 改动前 | 改动后 |
|------|--------|--------|
| 短对话（<10 轮）压缩开销 | 每次请求都执行 A 检查点 | 无开销（未超阈值不触发） |
| 长对话历史保留量 | 固定 32K（128K 模型） | 动态，最高 ~70K |
| 工具循环中途超限 | 硬停工具调用 | 先压缩，压缩后仍超才停 |
| 摘要质量 | 自由文本，无结构 | 6 段结构化 + 自压缩 |
| 高频对话摘要调用 | 每轮都调 LLM | 反抖动保护，最多 3 次 |
| 并发竞态 | 无保护 | Redis 锁 |
