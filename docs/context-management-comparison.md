# 六大框架上下文管理方案深度对比

## 源码路径速查 #

| 框架 | 仓库根目录 | 核心源码文件（相对路径） |
|---|---|---|
| **chat-agent** | `/Users/apple/Desktop/code/chat-agent` | `backend/app/utils/context_compactor.py` · `backend/app/utils/tool_result_hard_limit.py` · `backend/app/utils/history_truncate.py` · `backend/app/utils/token.py` · `backend/app/agents/chat_session_agent.py` · `backend/app/agents/tool_executor.py` · `backend/app/agents/utils/tavily_result_processor.py` · `backend/app/services/conversation/context_summary_service.py` · `backend/app/services/chat/history_context_service.py` · `backend/app/models/conversation_contexts_db.py` |
| **deer-flow** | `/Users/apple/Desktop/code/deer-flow` | `backend/packages/harness/deerflow/agents/middlewares/tool_output_budget_middleware.py` · `backend/packages/harness/deerflow/agents/middlewares/token_budget_middleware.py` · `backend/packages/harness/deerflow/agents/middlewares/token_usage_middleware.py` · `backend/packages/harness/deerflow/agents/middlewares/summarization_middleware.py` |
| **hermes-agent** | `~/.hermes/hermes-agent` | `agent/context_compressor.py` · `agent/context_engine.py` · `agent/conversation_compression.py` · `agent/model_metadata.py` · `tools/terminal_tool.py` |
| **claude-code** | `/Users/apple/Desktop/code/claude-code` | `src/utils/toolResultStorage.ts` · `src/constants/toolLimits.ts` · `src/services/compact/autoCompact.ts` · `src/services/compact/compact.ts` · `src/services/compact/microCompact.ts` · `src/services/compact/prompt.ts` · `src/services/compact/grouping.ts` · `src/utils/tokens.ts` · `src/utils/tokenBudget.ts` · `src/utils/truncate.ts` |
| **opencode** | `/Users/apple/Desktop/code/opencode` | `packages/opencode/src/tool/shell.ts` · `packages/opencode/src/tool/read.ts` · `packages/opencode/src/tool/truncate.ts` · `packages/opencode/src/session/compaction.ts` · `packages/opencode/src/session/overflow.ts` · `packages/opencode/src/session/processor.ts` · `packages/opencode/src/util/token.ts` · `packages/core/src/session/compaction.ts` · `packages/core/src/util/token.ts` |
| **codex (OpenAI)** | `/Users/apple/Desktop/code/codex` | `codex-rs/utils/output-truncation/src/lib.rs` · `codex-rs/core/src/context_manager/history.rs` · `codex-rs/core/src/session/context_window.rs` · `codex-rs/rollout-trace/src/compaction.rs` · `codex-rs/utils/string/src/truncate.rs` |

> **注意**: opencode 已从 Go 迁移为 TypeScript 项目（Effect + Drizzle）。上述路径均为当前 TypeScript 源码。

## 一、总览对比表 #

| 维度 | chat-agent | deer-flow | hermes-agent | claude-code | opencode | codex (OpenAI) |
|---|---|---|---|---|---|---|
| 语言 | Python (FastAPI) | Python (LangGraph) | Python (CLI) | TypeScript (Node) | TypeScript (Effect) | Rust (codex-rs) |
| 单轮工具结果压缩 | 硬上限落盘预览 + FAISS 语义截断（两层） | 磁盘外部化 + 头尾截断 | 头尾截断 + 摘要替换 | 磁盘持久化 + 预览 | 磁盘外部化 + 尾部截断 | 中间截断(truncate_middle)，每工具独立预算 |
| token 计数 | tiktoken (cl100k_base) | tiktoken + API usage_metadata | 字符估算 (÷4) + API 返回 | API usage + 字符估算 (÷4) | API usage + 字符估算 (÷4) 混合 | API usage 精确值 + 字节估算(÷4) 混合 |
| 阈值触发 | 硬上限(per-result 30K/turn 80K) + context_limit - max_output - 13K buffer → 四级渐进降级 | 硬停 100% (默认关闭) | 50% context → 压缩 | effective_window - 13K → 自动压缩 | input - min(20K, maxOutputTokens) → 自动摘要 | auto_compact_limit → Pre/Mid-Turn 自动压缩 |
| 窗口内历史处理 | token 预算切分(从新到旧累加整轮) | 消息数/token/比例触发摘要 | 头保护(3) + 尾保护(≥8消息) | 全量保留直到触发压缩 | 全量保留直到触发摘要 | 全量保留直到触发压缩 |
| 窗口外处理 | LLM 摘要(增量合并) | LLM 摘要(删除旧消息) | LLM 摘要(头+尾+中间摘要) | LLM 摘要(9段结构化) | LLM 摘要(替换历史) | LLM 摘要(替换历史) 或 Token Budget 直接重置 |
| 窗口内工具结果 | Step 2: summary 优先/2000 token 截断; Step 4: 最近 2 组保护, 旧组 head-tail 500/500 字符截断 | 历史重扫: 超预算重新截断 | 旧工具结果→1行摘要 | 时间触发清除 + 预算持久化 | prune: 保留 40K tokens 近期工具输出，旧的标记 compacted | 写入时一次性截断，后续原样保留 |

## 二、单轮调用：工具返回结果过长时的处理 #

### 2.1 chat-agent — 三层防护（硬上限落盘 + FAISS 语义截断 + 统一守卫兜底） #

chat-agent 的单轮工具结果压缩采用**三层递进**架构，每层处理不同粒度的问题：

**Layer 1 — 硬上限落盘预览（Agent 模式）**

核心文件: `backend/app/utils/tool_result_hard_limit.py`

```
Per-result 阈值:
  默认 max_chars = 30,000 chars（可按工具覆盖）
  覆盖: exec=20K, search_files=20K, web_site_crawl=20K, web_pages_extract=25K, load_skill=0(关闭)

Turn budget:
  turn_budget_chars = 80,000 chars（同轮全部工具结果合计）

操作:
  超阈值 → 完整内容写入 conversation workspace/.tool-results/{tool_call_id}.txt
  → 替换为 head(2000) + 省略标记 + tail(1000) + 文件路径提示
  → 模型可通过 read_file 回读完整原文

Fallback:
  落盘失败 → 头尾截断（按 max_chars 分配 head/tail 比例）

豁免: read_file（防 persist↔read 循环）
非 Agent 模式: 原样放行，由统一上下文守卫兜底
```

- Turn budget: 同轮工具结果执行完毕后，`enforce_turn_budget` 按大小排序从最大的开始强制落盘/截断，直到总 chars ≤ 80K
- Per-tool overrides: `ToolResultHardLimitConfig.tool_overrides` 支持按 LLM 名或 bare 名覆盖阈值，值为 0 表示关闭该工具单条上限

**Layer 2 — FAISS 语义截断（Markdown 工具结果）**

核心文件: `backend/app/utils/context_compactor.py`

```
策略: 语义相关性过滤
原理: 将工具结果按 Markdown 切块 → 向量化 → 与用户 query 计算相似度 → 贪心选择 top-K 块直到 token 预算
```

- 容错阈值 : tolerance_tokens = 8000（低于此不压缩）
- 目标阈值 : threshold_tokens = 5000
- chunk_size : 1024 字符, overlap 200 字符
- Fallback : 如果没选中任何 chunk，返回第一个 chunk

特殊处理: Tavily 搜索结果在 `TavilyResultProcessor` 中逐条调用 `compact_markdown_tool_result()` 压缩。

跳过压缩: `SKIP_TOOL_RESULT_COMPACTION_SERVERS` = `{file, shell, skill_manager}` — 这些 server 的结果不走 FAISS（shell/file 已由 Layer 1 硬上限处理）。

**Layer 3 — 统一上下文守卫兜底**

非 Agent 模式下不走 Layer 1/2，由 `unified_context_guard` 的 Step 2/4 统一兜底（见 3.1）。

特点: 唯一使用 语义相关性 而非纯机械截断的框架。保留与用户问题最相关的片段，而非简单的头尾。同时通过硬上限落盘实现类似 claude-code 的磁盘外部化，模型可通过 read_file 回读完整数据。

> **三层架构关系**: Layer 1（硬上限）在工具结果返回时立即触发（`apply_hard_limit`），Layer 2（FAISS）在同一 `_soft_shape_tool_result` 流程中对 markdown 结果触发，Layer 3（统一守卫）在每轮 LLM 调用前检查总 context。三者分别处理「单结果过大」「markdown 结果相关性过滤」「整体 context 超阈值」，互不依赖。

### 2.2 deer-flow — 两级策略（磁盘外部化 + 头尾截断） #

核心文件: `backend/.../tool_output_budget_middleware.py`

```
Tier 1 — 磁盘外部化 (preferred):
  触发: 结果 > 12,000 chars
  操作: 完整内容写入磁盘 .tool-results/，替换为 head(2000) + 文件引用 + tail(1000)

Tier 2 — Fallback 头尾截断:
  触发: 磁盘不可用时
  操作: 截断到 30,000 chars, head(8000) + 省略标记 + tail(3000)
```

- 行边界对齐 : `_snap_to_line_boundary()` 确保截断在换行处
- 豁免工具 : `read_file` 不做持久化（防循环）
- 历史重扫 : 每次模型调用前， `_patch_model_messages` 重新扫描历史中仍超预算的工具结果

### 2.3 hermes-agent — 头尾截断 + 工具结果摘要替换 #

核心文件: `tools/terminal_tool.py` , `agent/context_compressor.py`

```
终端输出截断:
  MAX_OUTPUT_CHARS = 50,000
  head(40%) + 截断通知 + tail(60%)

文件读取截断:
  MAX_LINES = 2,000, MAX_LINE_LENGTH = 2,000
  每行: line[:2000] + "..."
```

压缩预处理（无 LLM）:

- `_prune_old_tool_results()` : 旧工具结果替换为 1 行摘要，如 `[terminal] ran 'npm test' -> exit 0, 47 lines output`
- MD5 去重 : 相同工具结果只保留最新
- 工具调用参数截断 : `_truncate_tool_call_args_json()` — JSON 字符串值 >200 字符时压缩
- 图片替换 : 旧截图替换为 `[screenshot removed to save context]`

### 2.4 claude-code — 磁盘持久化 + 分层预算 #

核心文件: `src/utils/toolResultStorage.ts` , `src/constants/toolLimits.ts`

```
单工具预算: DEFAULT_MAX_RESULT_SIZE_CHARS = 50,000 chars
消息级预算: MAX_TOOL_RESULTS_PER_MESSAGE_CHARS = 200,000 chars
Token 上限: MAX_TOOL_RESULT_TOKENS = 100,000 (~400KB)
```

- 持久化 : 超阈值 → 写入 `tool-results/<tool_use_id>.txt` → 替换为 2KB 预览 + `<persisted-output>` 标签
- 消息级聚合 : 并行工具结果合计超 200K 时，最大结果优先持久化
- 确定性替换 : `ContentReplacementState` 确保已替换的结果在后续轮次保持一致（保护 prompt cache）
- Microcompact (时间触发) : 超过 60 分钟无交互的工具结果清除为 `[Old tool result content cleared]` ，保留最近 5 个
- 图片压缩 : `readImageWithTokenBudget()` — 先标准缩放，超 token 预算则激进压缩

### 2.5 opencode — 磁盘外部化 + 尾部截断 #

核心文件: `packages/opencode/src/tool/shell.ts` , `packages/opencode/src/tool/read.ts` , `packages/opencode/src/tool/truncate.ts`

```
Shell 输出截断 (tail-only):
  限制: maxLines=2000, maxBytes=50KB (来自 Truncate.limits()，可配置)
  截断方式: tail() — 仅保留尾部，丢弃头部
  磁盘持久化: 完整输出写入 TRUNCATION_DIR，返回尾部预览 + 文件路径提示
  Metadata 预览: MAX_METADATA_LENGTH = 30,000 chars (仅 UI 展示用)

文件读取截断:
  DEFAULT_READ_LIMIT = 2000 行, MAX_LINE_LENGTH = 2000, MAX_BYTES = 50KB
  截断后同样写入磁盘，返回预览 + offset 提示

Glob/Grep: 最多 100 个结果
```

- 截断服务 (`truncate.ts`) : 独立 Service，管理 `TRUNCATION_DIR` 下的截断文件，7 天自动清理
- 配置化 : `tool_output.max_lines` / `tool_output.max_bytes` 可在 opencode config 中覆盖
- Task 工具提示 : 如果 agent 有 task 工具权限，截断提示会建议委托给 explore agent 处理

特点: 与 deer-flow 类似的磁盘外部化模式。Shell 用尾部截断（保留最新输出），文件读取用头部截断（保留开头）。截断后完整数据持久化到磁盘，模型可通过 Grep/Read 工具重新访问。

### 2.6 codex (OpenAI) — 中间截断 + 分层预算 #

核心文件: `codex-rs/utils/output-truncation/src/lib.rs` , `codex-rs/core/src/context_manager/history.rs`

```
截断时机: 工具结果写入历史时一次性截断（非工具返回后立即截断）
截断算法: truncate_middle — 保留头部+尾部，中间替换为省略提示
截断策略: TruncationPolicy::Tokens(n) 或 ::Bytes(n)

// process_item 中使用 1.2x 容量系数，为序列化开销留余量
let policy_with_serialization_budget = policy * 1.2;
```

- 每工具独立预算 : 不同工具可在 `tools/context.rs` 中定义各自的 `TruncationPolicy`
- MCP 工具默认限制 : `Bytes(1024)`
- 批量写入 : 一轮采样结束后， `drain_in_flight` 批量等待所有 in-flight 工具完成，然后逐个写入历史并截断
- 多内容项处理 : `truncate_function_output_items_with_policy` 按顺序消耗 token 预算，超限的文本项被截断或省略，图片/音频按成本扣减

特点: 截断不是逐工具实时触发，而是 批量写入历史时统一处理。中间截断算法保证头尾信息保留，配合 1.2x 容量系数容忍序列化膨胀。

## 三、单轮结束后：Token 统计与阈值处理 #

### 3.1 chat-agent — 统一上下文守卫（四级渐进降级） #

核心文件: `backend/app/agents/chat_session_agent.py`（`unified_context_guard` 方法）

```
# 阈值计算（对齐 claude-code AUTOCOMPACT_BUFFER_TOKENS）
threshold = context_limit - min(max_output_tokens, 8192) - 13000
```

- Token 计数 : tiktoken `cl100k_base`（`TokenCalculator`），支持本地 BPE 文件离线回退
- 阈值设计 : `context_limit - max_output - 13K buffer`，与 claude-code 的 `effectiveContextWindow - 13000` 对齐

**四级渐进降级流程** :

```
Step 1: 检查 total_tokens <= threshold → 通过，无需操作

Step 2: 压缩所有历史轮次的工具结果
  - 优先使用已有 summary（LLM 摘要）
  - 无 summary 时：2000 token 头尾截断（head 60% / tail 40%）

Step 3: 按剩余预算切分历史消息窗口
  - 剩余预算 = threshold - system_tokens - user_tokens - tool_rounds_tokens
  - 从新到旧累加整轮（不拆分 user+assistant 对）
  - 窗口外消息 → LLM 增量摘要（合并到已有摘要）

Step 4: 按大小压缩当前轮次的工具结果（两阶段升级）
  - 阶段一: keep_recent=2（保护最近 2 组工具结果不动）
    旧组中 >threshold_chars 的结果按大小降序逐个 head-tail 500/500 字符截断，直到低于阈值
  - 阶段二: 若仍超阈值 → keep_recent=0（升级为压缩所有组）
  - 截断候选: 仅 tool_round_compressible_end 之前的 ToolResultMessage 且 len(content) > threshold_chars

最终: 若仍超阈值 → stop_tools（停止工具调用，切换到最终回答）
```

- 反抖动保护 : 3 次连续失败 → 进入 300s 恢复窗口（recovery window），期间不再尝试压缩
- 配置项 : `UnifiedContextGuardConfig`（`backend/app/schemas/config.py`）

### 3.2 deer-flow #

核心文件: `backend/.../token_budget_middleware.py`

```
# 默认关闭！需手动 enabled=True
max_tokens = 200,000          # 总量(input+output)
warn_threshold = 0.8          # 80% 软警告
hard_stop_threshold = 1.0     # 100% 硬停止
```

- 计数方式 : diff-based — 跟踪 `_seen_messages` 字典，只累加增量避免重复计数
- 软警告 : 注入 `HumanMessage(name="budget_warning")` 提示模型收尾
- 硬停止 : 剥离 `tool_calls` ，强制 `finish_reason="stop"`
- 子代理 token 合并 : `TokenUsageMiddleware` 将子代理的 `usage_metadata` 回溯合并到父消息

### 3.3 hermes-agent #

核心文件: `agent/context_compressor.py` , `agent/model_metadata.py`

```
# 字符估算 (无 tiktoken)
estimate_messages_tokens_rough(): (total_chars + 3) // 4 + image_tokens
_CHAR_PER_TOKEN = 4
IMAGE_TOKENS = 1500  # 每张图

# 阈值计算
threshold = effective_input_budget * threshold_percent  # 默认 50%
effective_input_budget = context_length - max_tokens    # 预留输出空间
MINIMUM_CONTEXT_LENGTH = 64K   # 最低阈值
```

- 三次检查点 : ① 轮次序言(preflight) ② 工具结果追加后(pre-API) ③ API 响应后(真实 token)
- API 真实值优先 : `update_from_response()` 使用 API 返回的 `prompt_tokens`
- 反抖动 : 2 次无效压缩后自动停止压缩
- 冷却机制 : 失败后 60s→300s→900s 递增冷却

### 3.4 claude-code #

核心文件: `src/services/compact/autoCompact.ts` , `src/utils/tokens.ts`

```
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

- JSON 特殊处理 : bytesPerToken=2（JSON 比普通文本 token 密度更高）
- 熔断器 : 3 次连续自动压缩失败后停止尝试
- 环境变量覆盖 : `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE` , `CLAUDE_CODE_AUTO_COMPACT_WINDOW`

### 3.5 opencode #

核心文件: `packages/opencode/src/session/overflow.ts` , `packages/opencode/src/session/compaction.ts` , `packages/core/src/util/token.ts`

```
// 双源 token 计数（与 claude-code 类似）
// overflow 检查: 使用 API 返回的 usage
const count = tokens.total || tokens.input + tokens.output
            + tokens.cache.read + tokens.cache.write
return count >= usable(input)

// compaction 选择: 使用客户端 chars÷4 估算
Token.estimate = (input: string) => Math.round(input.length / 4)

// 阈值: usable = input_limit - reserved
// reserved = min(COMPACTION_BUFFER=20000, maxOutputTokens)
// maxOutputTokens = min(model.output_limit, OUTPUT_TOKEN_MAX=***)
```

- 动态阈值 : 不是固定百分比。usable = input - min(20K, maxOutputTokens)。200K context 模型 → 180K (90%)；128K → 108K (84%)
- OUTPUT_TOKEN_MAX : 固定上限 32,000，`maxOutputTokens = min(model.output, 32000)`
- compaction 可通过 `compaction.auto: false` 关闭
- compaction 可配置独立 agent 用不同模型（`agents.get("compaction")`）
- 特点 : overflow 用 API 精确值，compaction 选择用客户端估算，两者分工明确

### 3.6 codex (OpenAI) #

核心文件: `codex-rs/core/src/session/context_window.rs` , `codex-rs/core/src/context_manager/history.rs`

```
// 双源 token 计数：服务端精确 + 本地估算
// 服务端: API 返回的 TokenUsage（input_tokens, total_tokens）
// 本地: approx_token_count = (byte_count + 3) / 4

// 阈值判定 — 两个条件取 OR
full_context_window_limit_reached = active_context_tokens >= context_window
token_limit_reached = (auto_compact_scope_tokens >= buffered_limit)
                    || full_context_window_limit_reached

// 两种 scope 模式
AutoCompactTokenLimitScope::Total       → 整个活跃上下文
AutoCompactTokenLimitScope::BodyAfterPrefix → 仅计算 prefix 之后增长部分
```

- 混合计数 : 服务端 API 返回精确 `TokenUsage` ，未覆盖的本地追加项用字节÷4 粗估
- 三阶段检查 : ① Pre-Turn（新一轮用户输入前）② Mid-Turn（每次采样后）③ Manual（用户手动触发）
- Buffered fallback : auto_compact_limit 外额外预留 fallback buffer，用尽后注入 fallback prompt
- Token Budget 模式 : 可选功能，压缩时直接重置上下文窗口而非 LLM 摘要
- 模型切换检测 : comp_hash 变化或 context window 缩小时自动触发 Pre-Turn 压缩

## 四、多轮调用时的历史上下文处理 #

### 4.1 窗口内上下文 #

| 框架 | 窗口定义 | 保留策略 |
|---|---|---|
| chat-agent | token 预算切分(从新到旧累加整轮) | remaining_budget = threshold - system - user - tool_rounds; 整轮累加直到预算耗尽 |
| deer-flow | messages:20 或 tokens/fraction 触发 | 二分查找安全切点，不拆分 AI+Tool 配对 |
| hermes-agent | 头保护(3条) + 尾保护(≥8条, token 预算) | 尾部按 token 预算向回走，对齐到 tool_call/tool_result 边界 |
| claude-code | 全量保留直到自动压缩 | 按 API round 分组，压缩时保留最近的 round |
| opencode | 全量保留直到 overflow | 摘要保留最近 2 轮(tail_turns)，旧消息→结构化 5 段摘要 |
| codex | 全量保留直到 auto_compact_limit | AutoCompactWindow 追踪窗口代际，prefill baseline 从服务端 usage 捕获 |

### 4.2 窗口外上下文 #

| 框架 | 处理方式 | 摘要策略 | 持久化 |
|---|---|---|---|
| chat-agent | LLM 摘要 | 增量合并（只摘要新增部分，合并到已有摘要）+ 摘要自压缩（prior >1.5x 预算时压缩） | DB`conversation_contexts` 表 |
| deer-flow | LLM 摘要 | 删除全部旧消息，插入 summary + 保留尾部 | 无额外持久化 |
| hermes-agent | LLM 摘要 | 结构化模板(Goal/Actions/State/Decisions)，迭代更新 | SQLite session 分割（旧 session 标记`compression` ） |
| claude-code | LLM 摘要 | 9 段结构化摘要(Primary Request/Key Concepts/Files/Errors/Pending/Next...) + 转录文件引用 | 写入磁盘转录文件，摘要中包含路径 |
| opencode | LLM 摘要 | 5 段结构化(Objective/Details/State/Next/Files) + 增量合并旧摘要 + 工具输出截断到 2K | compaction message (user role + compaction part) |
| codex | LLM 摘要 或 Token Budget 重置 | 用户消息 + 摘要替换整个历史；mid-turn 重新注入初始上下文(AGENTS.md等) | RolloutRecorder 持久化完整 rollout trace |

增量摘要（chat-agent、opencode 共有）:

```
# 如果已有摘要且只有新消息 → 只摘要增量 → 合并
if prior_summary and new_messages_only:
    delta_summary = llm.summarize(new_messages)
    merged = merge_summaries(prior_summary, delta_summary)
```

Anti-thrash 保护（chat-agent 独有）:

```
# 3 次连续摘要失败 → 300s 恢复期
# 摘要持久化时记录 last_summarized_message_ids 用于增量检测
# 摘要自压缩: prior_summary > max_tokens * 1.5 → 先压缩到 max_tokens // 2 再合并
```

Skill 救援（deer-flow 独有）:

```
# 从即将被摘要的历史中，抢救最近加载的 skill 文件
preserve_recent_skill_count = 5      # 最多救 5 个
preserve_recent_skill_tokens = 25000 # 总预算 25K
preserve_recent_skill_tokens_per_skill = 5000  # 每个 5K
```

文件恢复（claude-code 独有）:

```
POST_COMPACT_MAX_FILES_TO_RESTORE = 5
POST_COMPACT_TOKEN_BUDGET = 50,000  # 重新注入最近读取的文件
POST_COMPACT_SKILLS_TOKEN_BUDGET = 25,000  # 重新注入技能
```

### 4.3 窗口内的工具调用结果处理 #

| 框架 | 处理方式 |
|---|---|
| chat-agent | **写入时(硬上限)**: Agent 模式 per-result 30K chars → 落盘预览(head 2K+tail 1K+文件路径)，同轮 turn_budget 80K chars 强制从最大结果开始落盘。**写入时(语义)**: markdown 结果 >8K tokens → FAISS 语义截断到 5K。**Step 2(历史)**: ToolUseBlock args>500 chars → JSON 感知截断(保留 200 chars/string leaf)；ToolResultBlock: 优先用 summary，否则 >2000 tokens → head-tail 60/40 截断。**Step 4(当前轮)**: keep_recent=2 保护最近 2 组，旧组 head-tail 500/500 chars 截断(最大优先)；仍超→keep_recent=0 升级 |
| deer-flow | 窗口内保留原样；但`wrap_model_call` 每次调用前重新扫描，超预算的历史工具结果重新截断 |
| hermes-agent | 压缩预处理: 旧工具结果→1行摘要`[tool] ran 'cmd' -> exit N, M lines output` ；MD5 去重；图片→占位符 |
| claude-code | 时间触发: 60 分钟前的工具结果→`[Old tool result content cleared]` （保留最近 5 个）；API 层: 180K tokens 触发时清除旧结果 |
| opencode | prune 机制: 每轮结束后保留 40K tokens 近期工具输出，旧的标记 compacted；compaction 时工具输出截断到 2K |
| codex | 写入历史时一次性中间截断（1.2x 系数），后续原样保留，不做二次压缩或时间清理 |

## 五、架构特色对比 #

### 5.1 chat-agent 的独特之处 #

- 三层防护架构 : 硬上限落盘(per-result 30K + turn 80K) → FAISS 语义截断 → 统一守卫兜底，每层处理不同粒度
- 语义截断 : 唯一使用向量相似度筛选工具结果片段的框架
- 磁盘外部化 : 工具结果落盘到 conversation workspace/.tool-results/，模型可通过 read_file 回读完整原文（类似 claude-code/opencode）
- 增量摘要 : 窗口外摘要支持增量合并，避免重复摘要已有内容
- 摘要自压缩 : prior_summary 超预算 1.5x 时触发「摘要的摘要」压缩到 target/2
- 四级渐进降级 : 每次 LLM 调用前统一守卫，按'压缩历史工具结果 → 窗口化+摘要 → 压缩当前轮工具结果(两阶段升级) → 停止工具调用'逐级降级
- JSON 感知参数截断 : tool_use arguments 递归截断字符串叶子，保持 JSON 合法
- Per-tool 硬上限覆盖 : 支持按工具名定制阈值，灵活适配不同工具输出特征

### 5.2 deer-flow 的独特之处 #

- 中间件架构 : 所有逻辑通过 LangChain AgentMiddleware 组合，可插拔
- 磁盘外部化 : 工具结果持久化到文件，模型可通过 read_file 重新获取
- Skill 救援 : 摘要时抢救最近加载的 skill 文件
- 循环检测 : 窗口大小 20 的工具调用去重，阈值 3 次警告 / 5 次硬停
- 默认关闭 : token budget 和 summarization 默认 disabled

### 5.3 hermes-agent 的独特之处 #

- 字符估算优先 : 不依赖 tiktoken，用 `chars÷4` 粗估 + API 真实值校准
- 三阶段压缩 : ① 无 LLM 的工具结果剪枝 ② 边界确定 ③ LLM 摘要
- Session 分割 : 压缩后 SQLite session 物理分割，保留压缩谱系
- 反抖动机制 : 2 次无效压缩后停止，递增冷却时间
- 50% 阈值 : 最激进的压缩触发点（其他框架 80-95%）

### 5.4 claude-code 的独特之处 #

- 分层预算 : 单工具(50K) → 消息级(200K) → token(100K) 三级防护
- 确定性替换 : ContentReplacementState 冻结决策，保护 prompt cache
- Microcompact : 时间触发(60min) + 缓存感知的工具结果清理
- 9 段结构化摘要 : 最详细的摘要模板
- 熔断器 + 环境变量 : 3 次失败熔断，丰富的运行时配置覆盖

### 5.5 opencode 的独特之处 #

- 磁盘外部化 : 与 deer-flow 类似，截断后完整输出写入 `TRUNCATION_DIR`，7 天自动清理，模型可重新访问
- 结构化增量摘要 : 5 段模板(Objective/Important Details/Work State/Next Move/Relevant Files)，有旧摘要时增量合并
- 独立 compaction agent : 可配置更便宜的模型做摘要，与主模型分离
- Prune 机制 : 独立于 compaction 的工具输出清理，每轮结束后从尾部保留 40K tokens，旧工具输出标记 compacted
- 尾部保留 : compaction 时保留最近 `tail_turns`(默认 2) 轮，在 `preserve_recent_tokens`(2K-8K) 预算内
- 双源 token 计数 : overflow 检查用 API 精确值，compaction 选择用 chars÷4 估算

### 5.6 codex (OpenAI) 的独特之处 #

- 三种压缩模式可切换 : 本地 LLM 摘要 / 远程压缩 API / Token Budget 直接重置，通过 Feature Flag 选择
- Pre/Mid-Turn 双阶段自动压缩 : Pre-Turn 在用户输入前检查，Mid-Turn 在每次采样后检查，确保工具调用循环中也能及时压缩
- 模型切换自适应 : comp_hash 变化或 context window 缩小时自动触发压缩，保护跨模型会话
- AutoCompactWindow 代际追踪 : 通过 window_id (UUID v7) 追踪压缩代际，支持 resume/fork 时精确重建历史
- Rollout 持久化 : 完整对话历史写入 rollout trace，支持会话恢复和历史重建
- Buffered Fallback : auto_compact_limit 外预留 buffer，用尽后注入 fallback prompt 提示模型收尾
- 批量工具写入 : 一轮采样中所有工具结果暂存 in_flight 队列，采样结束后统一写入历史并截断

## 六、关键结论 #

### 6.1 复杂度排序（低→高） #

```
chat-agent(旧) < opencode < chat-agent < hermes-agent < codex < deer-flow < claude-code
```

> chat-agent 的复杂度因三层防护架构（硬上限 + FAISS + 统一守卫）显著提升，现介于 opencode 和 hermes-agent 之间。

### 6.2 工具结果压缩策略谱系 #

```
简单截断 ──────────────────────────────────── 语义压缩
opencode     codex    claude-code    chat-agent       hermes-agent    deer-flow
(磁盘外部化) (中间截断) (磁盘持久化) (落盘+FAISS语义)  (摘要+去重)    (外部化+重扫)
```

### 6.3 历史管理策略谱系 #

```
无管理 ──────────────────────────────────── 精细管理
opencode    claude-code    chat-agent    codex    hermes-agent    deer-flow
(tail保留+prune) (自动压缩) (三层+四级降级) (三模式切换) (三阶段压缩)  (中间件组合)
```

### 6.4 可借鉴的设计模式 #

| 模式 | 来源 | 适用场景 |
|---|---|---|
| 语义截断 | chat-agent | 工具结果很长但只需部分信息时 |
| 磁盘外部化 + 重取 | chat-agent, deer-flow, claude-code, opencode | 需要保留完整数据但不想占 context |
| 增量摘要 | chat-agent, opencode | 长对话频繁压缩时减少摘要成本 |
| Skill 救援 | deer-flow | 有频繁加载的参考文档场景 |
| 确定性替换 | claude-code | 依赖 prompt cache 的生产环境 |
| 时间触发清理 | claude-code | 长时间闲置后的自动清理 |
| 反抖动保护 | hermes-agent | 防止阈值附近反复压缩 |
| 模型切换自适应压缩 | codex | 跨模型会话自动降级压缩 |
| 批量工具写入 | codex | 一轮采样结束后统一截断，保证截断一致性 |
| Prune 工具输出 | opencode | 每轮结束后独立清理旧工具输出，与 compaction 解耦 |
| 结构化增量摘要 | opencode | 5 段模板 + 旧摘要合并，平衡结构化与增量效率 |
| 三模式压缩切换 | codex | 本地/远程/TokenBudget 按场景选择 |
| Session 分割 | hermes-agent | 需要保留完整对话历史的审计场景 |

## 七、chat-agent 可借鉴的改进方案 #

### 7.0 当前能力与缺口总览 #

```
✅ 已有能力:
  - 三层防护架构（硬上限落盘 + FAISS 语义截断 + 统一守卫兜底）
  - 硬上限落盘预览（Agent 模式 per-result 30K chars → workspace/.tool-results/，模型可 read_file 回读）
  - 同轮 turn budget（80K chars，按大小降序从最大结果开始落盘/截断）
  - Per-tool 硬上限覆盖（exec=20K, search_files=20K, web_pages_extract=25K 等）
  - FAISS 语义截断（markdown 工具结果实时压缩，tolerance=8K, target=5K）
  - tiktoken 精确计数（cl100k_base，支持本地 BPE 离线回退）
  - 四级渐进式上下文守卫（统一阈值 = context_limit - max_output - 13K buffer）
  - Step 4 两阶段升级（keep_recent=2 → keep_recent=0）
  - token 预算切分（从新到旧累加整轮）
  - 增量 LLM 摘要（含反抖动保护：3 次失败 → 300s 恢复）
  - 摘要自压缩（prior_summary 超 1.5x 预算时触发「摘要的摘要」）
  - tool_call 参数 JSON 感知截断（>500 chars, 保留 200 chars/叶子）
  - 当前轮工具结果 size-aware 压缩（保留最近 2 组，旧组 head-tail 500/500 字符）

❌ 存在缺口:
  - 长对话增量摘要质量退化，无结构化模板约束
  - 无时间触发的自动清理（老工具结果即使 <2000 tokens 也原样保留）
  - 无 prompt cache 保护（当前用 OpenAI 兼容 API，优先级低）
```

### 7.1 P0 — 必须修的 3 个问题 #

#### P0-1: 非 markdown 工具结果穿透 → 借鉴 claude-code 磁盘持久化

✅ **已实现**: `backend/app/utils/tool_result_hard_limit.py`

Agent 模式下，per-result 30K chars 超阈值时完整内容落盘到 `workspace/.tool-results/{tool_call_id}.txt`，替换为 head(2K) + tail(1K) + 文件路径提示。落盘失败时 fallback 到头尾截断。非 Agent 模式原样放行，由统一上下文守卫兜底。

`SKIP_TOOL_RESULT_COMPACTION_SERVERS` = `{file, shell, skill_manager}` 的 FAISS 压缩仍被跳过，但 shell/file 结果已由硬上限层处理，不再穿透。

配置项: `ToolResultHardLimitConfig`（`backend/app/schemas/config.py`），含 per-tool overrides、turn_budget_chars、exempt_bare_names 等。

#### P0-2: 单工具结果超 context 兜底 → 借鉴 hermes-agent 预检查

✅ **已实现**: `backend/app/utils/tool_result_hard_limit.py` 的 `enforce_turn_budget`

同轮工具结果执行完毕后，按大小降序从最大的开始强制落盘/截断，直到总 chars ≤ turn_budget_chars(80K)。与 P0-1 共用 `apply_hard_limit` 函数。三层防护完整覆盖：Layer 1 per-result → Layer 1 turn budget → Layer 3 unified guard。

#### P0-3: tool_call 参数压缩 → 借鉴 hermes-agent JSON 截断

✅ 已实现: Step 2 中 ToolUseBlock arguments JSON 感知截断 (>500 chars, 保留 200 chars/字符串叶子)。在 `compress_history_messages` 中对非最新一轮的历史 tool_call 执行截断，保持 JSON 合法。

### 7.2 P1 — 建议改进的 2 个问题 #

#### P1-1: 长对话摘要质量维护 → 借鉴 claude-code 结构化摘要 + hermes-agent 迭代压缩

问题: 增量摘要持续合并，早期信息被稀释。100+ 轮后摘要变成"什么都提了一句，什么都说不清楚"。 `summarize_merge` 的输入被截断到 `model_limit * 0.8` ，但 prior_summary 本身不截断，可能占满整个输入。

✅ **部分实现 — 摘要自压缩**: `context_summary_service.py` 的 `summarize_merge` 已实现 prior_summary 超预算 1.5x 时触发 `_compress_summary` 压缩到 `max_tokens // 2`，避免 prior_summary 占满输入。

借鉴 A: claude-code 的 9 段结构化摘要模板

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

借鉴 B: hermes-agent 的迭代摘要压缩

✅ **已实现**: `context_summary_service.py` 中 `_compress_summary` 方法在 prior_summary > max_tokens * 1.5 时触发自压缩。

剩余改进: 结构化摘要模板（上文借鉴 A）尚未实现，当前 LLM 自由输出。

改动范围: prompt 模板（结构化模板）
 预估工作量: 半天

#### P1-2: 工具结果时间触发清理 → 借鉴 claude-code microcompact

问题: 历史中 60 分钟前的工具结果仍占 context，只靠 `message_summary_threshold_tokens` （2000 tokens）截断。一个 1900 token 的老工具结果会原样保留。

借鉴: claude-code 的时间触发清理

| 维度 | claude-code | chat-agent 建议 |
|---|---|---|
| 触发条件 | 上次交互 > 60 分钟 | 工具结果创建时间 > 60 分钟 |
| 保留数量 | 最近 5 个工具结果完整保留 | 最近 5 个 |
| 清理方式 | `[Old tool result content cleared]` | `[工具结果已过期清除]` |
| 适用范围 | FileRead, Bash, Grep 等 | 所有 ToolResultBlock |

建议实现位置: `backend/app/services/chat/history_context_service.py` 的 `compress_history_messages` 中增加时间判断：

```
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

改动范围: `history_context_service.py`
 预估工作量: 1 小时

### 7.3 P2 — 锦上添花 #

#### P2-1: Prompt Cache 保护 → 借鉴 claude-code ContentReplacementState

仅在使用 Anthropic/Claude API 且开启 prompt caching 时有意义。核心思想：已替换的内容在后续轮次保持字节级一致，避免 cache 前缀失效。当前 chat-agent 用的是 OpenAI 兼容 API，优先级低。

#### P2-2: 反抖动保护 → 借鉴 hermes-agent

✅ 已实现: `UnifiedContextGuardConfig.anti_thrash_failure_threshold=3`, `anti_thrash_recovery_seconds=300`。连续 3 次压缩失败后停止压缩，进入 300s 恢复期。

### 7.4 改动优先级总表 #

| 优先级 | 编号 | 改动 | 借鉴来源 | 改动量 | 影响 | 状态 |
|---|---|---|---|---|---|---|
| P0 | P0-1 | 非 markdown 工具结果磁盘持久化 | claude-code | 中 | 防止 50K+ shell 输出撑爆 context | ✅ 已实现 |
| P0 | P0-2 | per-turn 聚合预算兜底 | hermes-agent | 小 | 防止单结果超 context API 报错 | ✅ 已实现 |
| P0 | P0-3 | tool_call 参数 JSON 感知截断 | hermes-agent | 小 | 保持 JSON 合法，减少参数膨胀 | ✅ 已实现 |
| P1 | P1-1 | 结构化摘要模板 + 摘要压缩 | claude-code + hermes-agent | 中 | 100+ 轮对话摘要质量维护 | 🔶 摘要压缩已实现，结构化模板待做 |
| P1 | P1-2 | 时间触发工具结果清理 | claude-code | 小 | 老工具结果自动释放 context | ❌ 未实现 |
| P2 | P2-1 | Prompt Cache 保护 | claude-code | 大 | 降低 API 成本（需 Anthropic） | ❌ 未实现（优先级低） |
| P2 | P2-2 | 反抖动保护 | hermes-agent | — | 防止阈值附近反复压缩 | ✅ 已实现 |

建议实施顺序: ~~P0-1 → P0-2~~ → P1-2 → P1-1(结构化模板) → P2-1
