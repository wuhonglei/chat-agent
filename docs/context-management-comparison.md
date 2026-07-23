# 五大框架上下文管理方案深度对比

> 研究日期: 2026-07-22
> 框架: chat-agent / deer-flow / hermes-agent / claude-code / opencode

---

## 一、总览对比表


| 维度           | chat-agent             | deer-flow                     | hermes-agent       | claude-code                   | opencode           |
| ------------ | ---------------------- | ----------------------------- | ------------------ | ----------------------------- | ------------------ |
| **语言**       | Python (FastAPI)       | Python (LangGraph)            | Python (CLI)       | TypeScript (Node)             | Go                 |
| **单轮工具结果压缩** | FAISS 语义截断             | 磁盘外部化 + 头尾截断                  | 头尾截断 + 摘要替换        | 磁盘持久化 + 预览                    | 头尾截断(前15K+后15K)    |
| **token 计数** | tiktoken (cl100k_base) | tiktoken + API usage_metadata | 字符估算 (÷4) + API 返回 | API usage + 字符估算 (÷4)         | 仅 API usage 返回     |
| **阈值触发**     | 80% context → 停工具调用    | 硬停 100% (默认关闭)                | 50% context → 压缩   | effective_window - 13K → 自动压缩 | 95% context → 自动摘要 |
| **窗口内历史处理**  | 轮次窗口(20轮) + token 裁剪   | 消息数/token/比例触发摘要              | 头保护(3) + 尾保护(≥8消息) | 全量保留直到触发压缩                    | 全量保留直到触发摘要         |
| **窗口外处理**    | LLM 摘要(增量合并)           | LLM 摘要(删除旧消息)                 | LLM 摘要(头+尾+中间摘要)   | LLM 摘要(9段结构化)                 | LLM 摘要(替换历史)       |
| **窗口内工具结果**  | 旧轮次: 用 summary 截断      | 历史重扫: 超预算重新截断                 | 旧工具结果→1行摘要         | 时间触发清除 + 预算持久化                | 原样保留直到摘要重置         |


---



## 二、单轮调用：工具返回结果过长时的处理



### 2.1 chat-agent — FAISS 语义截断

**核心文件:** `backend/app/utils/context_compactor.py`

```
策略: 语义相关性过滤
原理: 将工具结果按 Markdown 切块 → 向量化 → 与用户 query 计算相似度 → 贪心选择 top-K 块直到 token 预算
```

- **容错阈值**: tolerance_tokens = 6000（低于此不压缩）
- **目标阈值**: threshold_tokens = 5000
- **chunk_size**: 1000 字符, overlap 200 字符
- **Fallback**: 如果没选中任何 chunk，返回第一个 chunk

**特殊处理**: Tavily 搜索结果在 `TavilyResultProcessor` 中逐条调用 `compact_markdown_tool_result()` 压缩。

> **特点**: 唯一使用**语义相关性**而非纯机械截断的框架。保留与用户问题最相关的片段，而非简单的头尾。



### 2.2 deer-flow — 两级策略（磁盘外部化 + 头尾截断）

**核心文件:** `backend/.../tool_output_budget_middleware.py`

```
Tier 1 — 磁盘外部化 (preferred):
  触发: 结果 > 12,000 chars
  操作: 完整内容写入磁盘 .tool-results/，替换为 head(2000) + 文件引用 + tail(1000)

Tier 2 — Fallback 头尾截断:
  触发: 磁盘不可用时
  操作: 截断到 30,000 chars, head(8000) + 省略标记 + tail(3000)
```

- **行边界对齐**: `_snap_to_line_boundary()` 确保截断在换行处
- **豁免工具**: `read_file` 不做持久化（防循环）
- **历史重扫**: 每次模型调用前，`_patch_model_messages` 重新扫描历史中仍超预算的工具结果



### 2.3 hermes-agent — 头尾截断 + 工具结果摘要替换

**核心文件:** `tools/terminal_tool.py`, `agent/context_compressor.py`

```
终端输出截断:
  MAX_OUTPUT_CHARS = 50,000
  head(40%) + 截断通知 + tail(60%)

文件读取截断:
  MAX_LINES = 2,000, MAX_LINE_LENGTH = 2,000
  每行: line[:2000] + "... [truncated]"
```

**压缩预处理（无 LLM）:**

- `_prune_old_tool_results()`: 旧工具结果替换为 1 行摘要，如 `[terminal] ran 'npm test' -> exit 0, 47 lines output`
- **MD5 去重**: 相同工具结果只保留最新
- **工具调用参数截断**: `_truncate_tool_call_args_json()` — JSON 字符串值 >200 字符时压缩
- **图片替换**: 旧截图替换为 `[screenshot removed to save context]`



### 2.4 claude-code — 磁盘持久化 + 分层预算

**核心文件:** `src/utils/toolResultStorage.ts`, `src/constants/toolLimits.ts`

```
单工具预算: DEFAULT_MAX_RESULT_SIZE_CHARS = 50,000 chars
消息级预算: MAX_TOOL_RESULTS_PER_MESSAGE_CHARS = 200,000 chars
Token 上限: MAX_TOOL_RESULT_TOKENS = 100,000 (~400KB)
```

- **持久化**: 超阈值 → 写入 `tool-results/<tool_use_id>.txt` → 替换为 2KB 预览 + `<persisted-output>` 标签
- **消息级聚合**: 并行工具结果合计超 200K 时，最大结果优先持久化
- **确定性替换**: `ContentReplacementState` 确保已替换的结果在后续轮次保持一致（保护 prompt cache）
- **Microcompact (时间触发)**: 超过 60 分钟无交互的工具结果清除为 `[Old tool result content cleared]`，保留最近 5 个
- **图片压缩**: `readImageWithTokenBudget()` — 先标准缩放，超 token 预算则激进压缩



### 2.5 opencode — 简单头尾截断

**核心文件:** `internal/llm/tools/bash.go`, `internal/llm/tools/view.go`

```
Bash 输出: MAX_OUTPUT_LENGTH = 30,000 chars
  截断方式: 前 15K + "... [N lines truncated] ..." + 后 15K

文件读取: MAX_READ_SIZE = 250KB, DEFAULT_READ_LIMIT = 2000 行, MAX_LINE_LENGTH = 2000
Glob/Grep: 最多 100 个结果
```

> **特点**: 最简单的策略，无语义分析，无磁盘持久化，纯机械截断。

---



## 三、单轮结束后：Token 统计与阈值处理



### 3.1 chat-agent

**核心文件:** `backend/app/agents/chat_session_agent.py`, `backend/app/utils/token.py`

```python
# 每轮工具调用循环后检查
def _check_round_context_budget(self, next_round_messages):
    current_tokens = self.token_calculator.count_messages_tokens(next_round_messages)
    threshold_tokens = int(self.model_limit * self.tool_context_limit_ratio)  # 0.8
    return current_tokens > threshold_tokens, current_tokens, threshold_tokens
```

- **Token 计数**: tiktoken `cl100k_base`，支持本地 BPE 文件离线回退
- **工具轮阈值**: 80% context → 停止工具调用，切换到最终回答
- **历史 token 预算**: 25% context 分配给历史窗口



### 3.2 deer-flow

**核心文件:** `backend/.../token_budget_middleware.py`

```python
# 默认关闭！需手动 enabled=True
max_tokens = 200,000          # 总量(input+output)
warn_threshold = 0.8          # 80% 软警告
hard_stop_threshold = 1.0     # 100% 硬停止
```

- **计数方式**: diff-based — 跟踪 `_seen_messages` 字典，只累加增量避免重复计数
- **软警告**: 注入 `HumanMessage(name="budget_warning")` 提示模型收尾
- **硬停止**: 剥离 `tool_calls`，强制 `finish_reason="stop"`
- **子代理 token 合并**: `TokenUsageMiddleware` 将子代理的 `usage_metadata` 回溯合并到父消息



### 3.3 hermes-agent

**核心文件:** `agent/context_compressor.py`, `agent/model_metadata.py`

```python
# 字符估算 (无 tiktoken)
estimate_messages_tokens_rough(): (total_chars + 3) // 4 + image_tokens
_CHAR_PER_TOKEN = 4
IMAGE_TOKENS = 1500  # 每张图

# 阈值计算
threshold = effective_input_budget * threshold_percent  # 默认 50%
effective_input_budget = context_length - max_tokens    # 预留输出空间
MINIMUM_CONTEXT_LENGTH = 64K   # 最低阈值
```

- **三次检查点**: ① 轮次序言(preflight) ② 工具结果追加后(pre-API) ③ API 响应后(真实 token)
- **API 真实值优先**: `update_from_response()` 使用 API 返回的 `prompt_tokens`
- **反抖动**: 2 次无效压缩后自动停止压缩
- **冷却机制**: 失败后 60s→300s→900s 递增冷却



### 3.4 claude-code

**核心文件:** `src/services/compact/autoCompact.ts`, `src/utils/tokens.ts`

```typescript
// token 计数: API usage + 字符估算混合
tokenCountWithEstimation():
  lastAPICallUsage.input_tokens + cache_creation + cache_read + output_tokens
  + roughTokenCountEstimationForMessages(new_messages)  // ÷4

// 阈值
effectiveContextWindow = contextWindow - min(maxOutputTokens, 20,000)
autoCompactThreshold = effectiveContextWindow - 13,000  // AUTOCOMPACT_BUFFER
warningThreshold = threshold - 20,000
blockingLimit = effectiveContextWindow - 3,000
```

- **JSON 特殊处理**: bytesPerToken=2（JSON 比普通文本 token 密度更高）
- **熔断器**: 3 次连续自动压缩失败后停止尝试
- **环境变量覆盖**: `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE`, `CLAUDE_CODE_AUTO_COMPACT_WINDOW`



### 3.5 opencode

**核心文件:** `internal/tui/tui.go`, `internal/llm/agent/agent.go`

```go
// 仅使用 API 返回的 usage，无客户端 token 计算
tokens := session.CompletionTokens + session.PromptTokens
if tokens >= int64(float64(contextWindow) * 0.95) && config.Get().AutoCompact {
    startCompactSession()
}
```

- **95% 阈值**: 累计 token 达到 context window 的 95% 时触发自动摘要
- **MaxTokens 上限**: 如果 `maxTokens > ContextWindow/2`，自动限制为一半
- **特点**: 最轻量的方案，完全依赖 API 返回值，无客户端估算

---



## 四、多轮调用时的历史上下文处理



### 4.1 窗口内上下文


| 框架               | 窗口定义                             | 保留策略                                         |
| ---------------- | -------------------------------- | -------------------------------------------- |
| **chat-agent**   | 最近 20 轮(user+assistant 对)        | 轮次计数 + token 预算裁剪(25% context)               |
| **deer-flow**    | messages:20 或 tokens/fraction 触发 | 二分查找安全切点，不拆分 AI+Tool 配对                      |
| **hermes-agent** | 头保护(3条) + 尾保护(≥8条, token 预算)     | 尾部按 token 预算向回走，对齐到 tool_call/tool_result 边界 |
| **claude-code**  | 全量保留直到自动压缩                       | 按 API round 分组，压缩时保留最近的 round                |
| **opencode**     | 全量保留直到 95% 阈值                    | 摘要后 SummaryMessageID 之前的全部丢弃                 |




### 4.2 窗口外上下文


| 框架               | 处理方式   | 摘要策略                                                                         | 持久化                                           |
| ---------------- | ------ | ---------------------------------------------------------------------------- | --------------------------------------------- |
| **chat-agent**   | LLM 摘要 | 增量合并（只摘要新增部分，合并到已有摘要）                                                        | DB `conversation_contexts` 表                  |
| **deer-flow**    | LLM 摘要 | 删除全部旧消息，插入 summary + 保留尾部                                                    | 无额外持久化                                        |
| **hermes-agent** | LLM 摘要 | 结构化模板(Goal/Actions/State/Decisions)，迭代更新                                     | SQLite session 分割（旧 session 标记 `compression`） |
| **claude-code**  | LLM 摘要 | 9 段结构化摘要(Primary Request/Key Concepts/Files/Errors/Pending/Next...) + 转录文件引用 | 写入磁盘转录文件，摘要中包含路径                              |
| **opencode**     | LLM 摘要 | 独立摘要模型(可用便宜模型)生成摘要                                                           | SummaryMessageID 存储在 session 记录               |


**增量摘要（chat-agent 独有）:**

```python
# 如果已有摘要且只有新消息 → 只摘要增量 → 合并
if prior_summary and new_messages_only:
    delta_summary = llm.summarize(new_messages)
    merged = merge_summaries(prior_summary, delta_summary)
```

**Skill 救援（deer-flow 独有）:**

```python
# 从即将被摘要的历史中，抢救最近加载的 skill 文件
preserve_recent_skill_count = 5      # 最多救 5 个
preserve_recent_skill_tokens = 25000 # 总预算 25K
preserve_recent_skill_tokens_per_skill = 5000  # 每个 5K
```

**文件恢复（claude-code 独有）:**

```
POST_COMPACT_MAX_FILES_TO_RESTORE = 5
POST_COMPACT_TOKEN_BUDGET = 50,000  # 重新注入最近读取的文件
POST_COMPACT_SKILLS_TOKEN_BUDGET = 25,000  # 重新注入技能
```



### 4.3 窗口内的工具调用结果处理


| 框架               | 处理方式                                                                                        |
| ---------------- | ------------------------------------------------------------------------------------------- |
| **chat-agent**   | 窗口内旧轮次: 有 summary 则替换 content；无 summary 且 >2000 tokens 则截断 + `[内容已截断]`；**最新工具轮不处理**         |
| **deer-flow**    | 窗口内保留原样；但 `wrap_model_call` 每次调用前重新扫描，超预算的历史工具结果重新截断                                        |
| **hermes-agent** | 压缩预处理: 旧工具结果→1行摘要 `[tool] ran 'cmd' -> exit N, M lines output`；MD5 去重；图片→占位符                |
| **claude-code**  | 时间触发: 60 分钟前的工具结果→`[Old tool result content cleared]`（保留最近 5 个）；API 层: 180K tokens 触发时清除旧结果 |
| **opencode**     | 原样保留在历史中，直到 95% 阈值触发整体摘要重置                                                                  |


---



## 五、架构特色对比



### 5.1 chat-agent 的独特之处

- **语义截断**: 唯一使用向量相似度筛选工具结果片段的框架
- **增量摘要**: 窗口外摘要支持增量合并，避免重复摘要已有内容
- **Token 分区**: 严格划分 — 历史占 25%，工具轮 80% 触发停止



### 5.2 deer-flow 的独特之处

- **中间件架构**: 所有逻辑通过 LangChain AgentMiddleware 组合，可插拔
- **磁盘外部化**: 工具结果持久化到文件，模型可通过 read_file 重新获取
- **Skill 救援**: 摘要时抢救最近加载的 skill 文件
- **循环检测**: 窗口大小 20 的工具调用去重，阈值 3 次警告 / 5 次硬停
- **默认关闭**: token budget 和 summarization 默认 disabled



### 5.3 hermes-agent 的独特之处

- **字符估算优先**: 不依赖 tiktoken，用 `chars÷4` 粗估 + API 真实值校准
- **三阶段压缩**: ① 无 LLM 的工具结果剪枝 ② 边界确定 ③ LLM 摘要
- **Session 分割**: 压缩后 SQLite session 物理分割，保留压缩谱系
- **反抖动机制**: 2 次无效压缩后停止，递增冷却时间
- **50% 阈值**: 最激进的压缩触发点（其他框架 80-95%）



### 5.4 claude-code 的独特之处

- **分层预算**: 单工具(50K) → 消息级(200K) → token(100K) 三级防护
- **确定性替换**: ContentReplacementState 冻结决策，保护 prompt cache
- **Microcompact**: 时间触发(60min) + 缓存感知的工具结果清理
- **9 段结构化摘要**: 最详细的摘要模板
- **熔断器 + 环境变量**: 3 次失败熔断，丰富的运行时配置覆盖



### 5.5 opencode 的独特之处

- **最简方案**: 无客户端 token 计数，无分层预算，无中间件
- **纯摘要重置**: 95% → 摘要 → 清空，一步到位
- **独立摘要模型**: 可配置更便宜的模型做摘要

---



## 六、关键结论



### 6.1 复杂度排序（低→高）

```
opencode < chat-agent < hermes-agent < deer-flow < claude-code
```



### 6.2 工具结果压缩策略谱系

```
简单截断 ────────────────────────────── 语义压缩
opencode    claude-code    hermes-agent    deer-flow    chat-agent
(头尾截断)  (磁盘持久化)   (摘要+去重)    (外部化+重扫) (FAISS语义筛选)
```



### 6.3 历史管理策略谱系

```
无管理 ─────────────────────────────── 精细管理
opencode    claude-code    hermes-agent    chat-agent    deer-flow
(全量→摘要)  (自动压缩)    (三阶段压缩)  (轮次窗口+摘要) (中间件组合)
```



### 6.4 可借鉴的设计模式


| 模式         | 来源                     | 适用场景                  |
| ---------- | ---------------------- | --------------------- |
| 语义截断       | chat-agent             | 工具结果很长但只需部分信息时        |
| 磁盘外部化 + 重取 | deer-flow, claude-code | 需要保留完整数据但不想占 context  |
| 增量摘要       | chat-agent             | 长对话频繁压缩时减少摘要成本        |
| Skill 救援   | deer-flow              | 有频繁加载的参考文档场景          |
| 确定性替换      | claude-code            | 依赖 prompt cache 的生产环境 |
| 时间触发清理     | claude-code            | 长时间闲置后的自动清理           |
| 反抖动保护      | hermes-agent           | 防止阈值附近反复压缩            |
| Session 分割 | hermes-agent           | 需要保留完整对话历史的审计场景       |


---


## 七、chat-agent 可借鉴的改进方案


### 7.0 当前能力与缺口总览


```
✅ 已有能力:
  - FAISS 语义截断（markdown 工具结果）
  - tiktoken 精确计数
  - 80% 阈值停止工具调用
  - 20 轮滑动窗口 + 25% token 预算
  - 增量 LLM 摘要

❌ 存在缺口:
  - 非 markdown 工具结果（shell/JSON）无压缩，直接穿透
  - 单个工具结果超 context 无兜底，可能 API 报错
  - tool_call 参数（如 write_file 大代码）从不压缩
  - 长对话增量摘要质量退化，无重压缩机制
  - 无时间触发的自动清理
  - 无 prompt cache 保护
  - 无反抖动保护
```



### 7.1 P0 — 必须修的 3 个问题


#### P0-1: 非 markdown 工具结果穿透 → 借鉴 claude-code 磁盘持久化


**问题:**

`shell`/`file` MCP 被排除在压缩之外（`mcp/constants.py` 的 `SKIP_TOOL_RESULT_COMPACTION_SERVERS`），50K 的 shell 输出直接塞进 context。非 markdown 的自定义 MCP 工具结果走 FAISS markdown splitter，chunk 质量很差。


**借鉴: claude-code 的 `maybePersistLargeToolResult()`**

| 维度        | claude-code 实现                            | chat-agent 建议                    |
| --------- | ---------------------------------------- | ------------------------------- |
| 单工具阈值     | 50,000 chars                             | 30,000 chars                    |
| 操作        | 写磁盘 → 替换为 2KB 预览 + `<persisted-output>` 标签 | 写磁盘 → 替换为预览 + 文件路径              |
| 消息级聚合     | 200,000 chars（并行工具合计）                    | 暂不需要，chat-agent 工具串行执行         |
| 确定性替换     | ContentReplacementState 冻结决策             | 暂不需要（无 prompt cache）            |
| 豁免工具      | `read_file`（防循环）                        | `read_file`、`read_file_tool` |

**建议实现位置:** `backend/app/agents/tool_executor.py`，在 `_compact_tool_result_if_needed` 之后增加统一拦截：

```python
# 伪代码
MAX_TOOL_RESULT_CHARS = 30_000
PREVIEW_CHARS = 2_000

def _persist_if_too_large(self, tool_result, tool_call_id):
    if len(tool_result.content) > MAX_TOOL_RESULT_CHARS:
        path = f"/tmp/chat-agent-results/{tool_call_id}.txt"
        write_to_disk(path, tool_result.content)
        preview = tool_result.content[:PREVIEW_CHARS]
        tool_result.content = (
            f"{preview}\n\n"
            f"[完整输出已保存到 {path}，共 {len(tool_result.content)} 字符，"
            f"约 {len(tool_result.content) // 4} tokens。"
            f"需要查看具体内容时可用 read_file 工具读取。]"
        )
        tool_result.truncated = True
```

**改动范围:** `tool_executor.py` + `schemas/config.py`（新增 `ToolResultPersistConfig`）
**预估工作量:** 半天


#### P0-2: 单工具结果超 context 兜底 → 借鉴 hermes-agent 预检查


**问题:**

工具结果追加后，只在下一轮 `_check_round_context_budget` 才检查。如果单个结果 > context，直接 API 报错，无 try/catch。


**借鉴: hermes-agent 的三层防护**

| 层级      | hermes-agent                              | chat-agent 现状  | 建议  |
| ------- | ----------------------------------------- | ------------- | --- |
| Layer 1 | 每个工具内部截断                               | ✅ 已有         | —   |
| Layer 2 | per-result 持久化（`maybe_persist_tool_result`） | ❌ 缺失（P0-1 解决） | 加   |
| Layer 3 | per-turn 聚合预算（`enforce_turn_budget`）       | ❌ 缺失         | 加   |

**建议实现位置:** `backend/app/agents/tool_executor.py`，在所有工具执行完毕后：

```python
def _enforce_turn_budget(self, tool_round_messages, context_limit):
    total_chars = sum(len(m.content) for m in tool_round_messages)
    budget = int(context_limit * 0.5)  # 工具轮最多占 50% context
    if total_chars > budget:
        # 按大小排序，从最大的开始持久化，直到低于预算
        sorted_msgs = sorted(tool_round_messages, key=lambda m: len(m.content), reverse=True)
        for msg in sorted_msgs:
            if total_chars <= budget:
                break
            original_len = len(msg.content)
            self._persist_if_too_large(msg, msg.tool_call_id)  # 复用 P0-1 的函数
            total_chars -= original_len - len(msg.content)
```

**改动范围:** `tool_executor.py`（复用 P0-1 的持久化函数）
**预估工作量:** 2 小时


#### P0-3: tool_call 参数压缩 → 借鉴 hermes-agent JSON 截断


**问题:**

LLM 生成 `write_file(content="50K 代码")` 后，参数永久留在 context 中。token 计数虽然覆盖了 `tool_calls`，但从不压缩。


**借鉴: hermes-agent 的 `_truncate_tool_call_args_json()`**

| 维度 | hermes-agent                    | chat-agent 建议                        |
| -- | ------------------------------- | ----------------------------------- |
| 阈值 | 字符串值 > 200 chars                | 字符串值 > 500 chars                    |
| 操作 | 截断 value，保持 JSON 合法             | 同左                                   |
| 时机 | 压缩预处理阶段（`_prune_old_tool_results`） | `compress_history_messages` 中         |

**建议实现位置:** `backend/app/services/chat/history_context_service.py` 的 `compress_history_messages` 中：

```python
def _truncate_tool_call_args(self, tool_calls, max_arg_len=500):
    """截断 tool_call 中的大参数值，保持 JSON 合法"""
    for tc in tool_calls:
        if not tc.get("function", {}).get("arguments"):
            continue
        try:
            args = json.loads(tc["function"]["arguments"])
        except (json.JSONDecodeError, TypeError):
            continue
        changed = False
        for k, v in args.items():
            if isinstance(v, str) and len(v) > max_arg_len:
                args[k] = v[:200] + f"... [{len(v)} chars, truncated]"
                changed = True
        if changed:
            tc["function"]["arguments"] = json.dumps(args, ensure_ascii=False)
```

仅对**非最新一轮**的历史 tool_call 执行，最新一轮保持完整。

**改动范围:** `history_context_service.py`
**预估工作量:** 1 小时



### 7.2 P1 — 建议改进的 2 个问题


#### P1-1: 长对话摘要质量维护 → 借鉴 claude-code 结构化摘要 + hermes-agent 迭代压缩


**问题:**

增量摘要持续合并，早期信息被稀释。100+ 轮后摘要变成"什么都提了一句，什么都说不清楚"。`summarize_merge` 的输入被截断到 `model_limit * 0.8`，但 prior_summary 本身不截断，可能占满整个输入。


**借鉴 A: claude-code 的 9 段结构化摘要模板**

当前 chat-agent 的摘要没有结构约束，LLM 自由输出。建议固定结构：

```
## 主要需求
用户的核心目标和诉求

## 已完成工作
已经解决的问题和交付的内容

## 进行中
当前正在处理的任务

## 待处理
用户提出但尚未完成的需求

## 关键决策
对话中做出的重要技术/方案决策

## 关键上下文
后续对话可能需要的背景信息
```

**借鉴 B: hermes-agent 的迭代摘要压缩**

当累积摘要超过预算时，触发"摘要的摘要"：

```python
# 在 context_summary_service.py 的 summarize_merge 中
SUMMARY_MAX_TOKENS = 1000
SUMMARY_WARN_RATIO = 1.5

prior_tokens = self.token_calculator.count_tokens(prior_summary)
if prior_tokens > SUMMARY_MAX_TOKENS * SUMMARY_WARN_RATIO:
    # 先压缩 prior_summary 本身
    prior_summary = self._compress_summary(prior_summary, SUMMARY_MAX_TOKENS // 2)
# 再合并新内容
merged = self._merge_summaries(prior_summary, new_messages)
```

**改动范围:** `context_summary_service.py` + prompt 模板
**预估工作量:** 半天


#### P1-2: 工具结果时间触发清理 → 借鉴 claude-code microcompact


**问题:**

历史中 60 分钟前的工具结果仍占 context，只靠 `message_summary_threshold_tokens`（2000 tokens）截断。一个 1900 token 的老工具结果会原样保留。


**借鉴: claude-code 的时间触发清理**

| 维度   | claude-code                        | chat-agent 建议     |
| ---- | ---------------------------------- | ---------------- |
| 触发条件 | 上次交互 > 60 分钟                       | 工具结果创建时间 > 60 分钟   |
| 保留数量 | 最近 5 个工具结果完整保留                     | 最近 5 个             |
| 清理方式 | `[Old tool result content cleared]` | `[工具结果已过期清除]`    |
| 适用范围 | FileRead, Bash, Grep 等             | 所有 ToolResultBlock |

**建议实现位置:** `backend/app/services/chat/history_context_service.py` 的 `compress_history_messages` 中增加时间判断：

```python
import time

TOOL_RESULT_MAX_AGE_SECONDS = 3600  # 60 分钟
TOOL_RESULT_KEEP_RECENT = 5

def _cleanup_stale_tool_results(self, messages):
    """清理过期的工具结果，保留最近 N 个"""
    tool_result_indices = []
    for i, msg in enumerate(messages):
        if msg.role == "tool":
            tool_result_indices.append(i)

    # 保留最近 N 个
    stale_indices = tool_result_indices[:-TOOL_RESULT_KEEP_RECENT]
    for idx in stale_indices:
        msg = messages[idx]
        age = time.time() - msg.created_at.timestamp()
        if age > TOOL_RESULT_MAX_AGE_SECONDS and len(msg.content) > 200:
            msg.content = "[工具结果已过期清除]"
            msg.summary = None
```

**改动范围:** `history_context_service.py`
**预估工作量:** 1 小时



### 7.3 P2 — 锦上添花


#### P2-1: Prompt Cache 保护 → 借鉴 claude-code ContentReplacementState

仅在使用 Anthropic/Claude API 且开启 prompt caching 时有意义。核心思想：已替换的内容在后续轮次保持字节级一致，避免 cache 前缀失效。当前 chat-agent 用的是 OpenAI 兼容 API，优先级低。

#### P2-2: 反抖动保护 → 借鉴 hermes-agent

如果 context 在阈值附近波动，可能反复触发摘要。hermes-agent 的方案：连续 2 次压缩后 token 仍超标 → 停止压缩，进入冷却（60s→300s→900s 递增）。实现简单，建议在 `chat_session_agent.py` 的压缩触发处增加计数器。



### 7.4 改动优先级总表


| 优先级 | 编号   | 改动                   | 借鉴来源                   | 改动量   | 影响                          | 文件                                  |
| ---- | ---- | -------------------- | ---------------------- | ----- | --------------------------- | ----------------------------------- |
| P0   | P0-1 | 非 markdown 工具结果磁盘持久化 | claude-code            | 中（半天） | 防止 50K+ shell 输出撑爆 context  | `tool_executor.py`, `config.py`     |
| P0   | P0-2 | per-turn 聚合预算兜底     | hermes-agent           | 小（2h） | 防止单结果超 context API 报错        | `tool_executor.py`                  |
| P0   | P0-3 | tool_call 大参数截断     | hermes-agent           | 小（1h） | 防止大参数永久占 context            | `history_context_service.py`        |
| P1   | P1-1 | 结构化摘要模板 + 摘要压缩    | claude-code + hermes-agent | 中（半天） | 100+ 轮对话摘要质量维护             | `context_summary_service.py`, prompt |
| P1   | P1-2 | 时间触发工具结果清理         | claude-code            | 小（1h） | 老工具结果自动释放 context          | `history_context_service.py`        |
| P2   | P2-1 | Prompt Cache 保护     | claude-code            | 大      | 降低 API 成本（需 Anthropic）      | 多文件                                |
| P2   | P2-2 | 反抖动保护               | hermes-agent           | 小（30min） | 防止阈值附近反复压缩                 | `chat_session_agent.py`             |

**建议实施顺序:** P0-3 → P0-1 → P0-2 → P1-2 → P1-1 → P2-2 → P2-1

（从最小改动、最高收益开始）
