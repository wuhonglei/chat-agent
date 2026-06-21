# Langfuse chat-turn 延迟分析报告

- **用户**: `3a30e647-c46a-4f2e-ae1a-665d6a7b7cde`
- **环境**: prod
- **时间范围**: 2026-06-19 ~ 2026-06-21
- **Langfuse 控制台**: https://langfuse.wuhonglei.cn/project/cmpwh4pcg0002qn07mv4f20af/users/3a30e647-c46a-4f2e-ae1a-665d6a7b7cde

---

## 1. 总体概览

| 指标 | 值 |
|------|-----|
| chat-turn traces 总数 | 108 |
| 总 observations | 933 |
| GENERATION | 301 |
| SPAN | 544 |
| TOOL | 88 |

## 2. chat-turn 端到端延迟

| 指标 | 值 |
|------|-----|
| P50 | 18.0s |
| P75 | 27.1s |
| P90 | 38.8s |
| P95 | 48.2s |
| P99 | 54.2s |
| 平均 | 20.4s |
| 最小 | 2.0s |
| 最大 | 80.1s |

## 3. 延迟构成（平均值）

```
总延迟:    20.4s (100%)
├── LLM 调用:   10.9s (53%)  ← 主要瓶颈
├── Tool 执行:   6.3s (31%)  ← 第二大瓶颈
└── 其他开销:    3.2s (16%)  ← memory-search / title-gen / 网络等
```

**中位数构成：**

| 分类 | 延迟 | 占比 |
|------|------|------|
| 总延迟 | 18.0s | 100% |
| LLM 调用 | 10.7s | 60% |
| Tool 执行 | 4.8s | 27% |
| 其他开销 | 0.7s | 4% |

## 4. LLM 调用分析

平均每 turn 调用 **2.8 次** LLM。

### 4.1 按模型统计

| 模型 | 调用次数 | 平均延迟 | P90 | Input tokens/call | Output tokens/call |
|------|---------|---------|-----|-------------------|--------------------|
| deepseek-v4-flash | 192 | 5.85s | 13.02s | 9,849 | 522 |
| qwen3.5-flash | 108 | 0.50s | 0.64s | 245 | 8 |
| deepseek-v4-pro | 1 | 1.66s | — | 3,254 | 77 |

- `deepseek-v4-flash` 是主对话模型
- `qwen3.5-flash` 用于标题生成（每 turn 固定 1 次）

### 4.2 deepseek-v4-flash Token 数 vs 延迟

| Token 范围 | 调用数 | 平均延迟 |
|-----------|--------|---------|
| 2K – 5K | 109 | 3.2s |
| 5K – 10K | 13 | 5.8s |
| 10K – 20K | 31 | 8.9s |
| 20K – 50K | 38 | 10.6s |

> 输入 token 数与延迟正相关，长上下文是主要延迟来源。当前 avg 9.8K tokens/call，长上下文（10K+）占比 36%。

### 4.3 deepseek-v4-flash Token 分布

| 指标 | Input tokens | Output tokens |
|------|-------------|---------------|
| 最小 | 2,750 | 43 |
| 中位数 | 3,437 | 314 |
| 平均 | 9,849 | 522 |
| 最大 | 60,638 | 2,202 |

## 5. Tool 执行延迟

| Tool | 调用次数 | 平均延迟 | 最大延迟 |
|------|---------|---------|---------|
| code_execute_code | 7 | 10.0s | 22.5s |
| tavily_web_pages_extract | 6 | 9.3s | 29.1s |
| tavily_web_search | 73 | 7.6s | 34.4s |
| weather_get_current_weather | 1 | 3.7s | 3.7s |
| weather_search_city | 1 | 0.2s | 0.2s |

## 6. 子 Span 延迟

| Span | 平均延迟 | 说明 |
|------|---------|------|
| history-prepare | ~0ms | 几乎无开销 |
| memory-search | ~660ms | P50=580ms, max=4.5s |
| kb-rag-build | ~0ms | 几乎无开销 |
| title-generation | ~500ms | 同步调用 qwen3.5-flash |

## 7. 时间趋势

| 时间段 | 样本数 | 平均延迟 | 中位延迟 | 最大延迟 |
|--------|-------|---------|---------|---------|
| 06-19 11:00 | 63 | 13.3s | 12.2s | 40.7s |
| 06-19 12:00 | 8 | 21.7s | 21.7s | 31.2s |
| 06-19 13:00 | 36 | 32.9s | 28.1s | 80.1s |
| 06-21 04:00 | 1 | 10.0s | 10.0s | 10.0s |

> 06-19 13:00 出现延迟飙升，20/36 请求 > 30s。

## 8. 慢请求分析（>30s）

共 **20 个**慢请求，特征：

- 100% 使用 `tavily_web_search` 或 `code_execute_code`
- 平均 3.4 次 LLM 调用 + 1.6 次 Tool 调用
- 典型场景：调研类问题（需要多次搜索 + 代码执行）

**最慢的 3 个请求：**

| 排名 | 延迟 | 输入 | LLM 调用 | Tool 调用 |
|------|------|------|---------|----------|
| 1 | 80.1s | 采样数据分析（3382/5672/48 采样） | 5 gen | 3 code_execute |
| 2 | 73.9s | 公司调研：Superlinear/Lessie AI | 3 gen | 1 tavily_search |
| 3 | 54.2s | 技术调研：StackBlitz WebContainers + Next.js | 3 gen | 1 tavily_search |

## 9. 快速请求（<5s）

仅 **13 个**（12%），平均 3.7s。这些是无 tool 调用的纯对话，2 次 LLM 调用（主对话 + 标题）。

## 10. 上下文来源深度分析（avg 9,849 tokens/call 从哪来）

### 10.1 每轮 chat-turn 的 LLM 调用序列

| 调用位置 | 模型 | 触发率 | Input tokens | 说明 |
|---------|------|--------|-------------|------|
| Position 1 | qwen3.5-flash | 108/108 | avg 246 | 标题生成（固定） |
| Position 2 | deepseek-v4-flash | 107/108 | avg 3,010, median 2,766 | 决策调用：是否调用工具 |
| Position 3 | deepseek-v4-flash | 72/108 | avg 18,604, median 18,258 | 响应调用：拿到工具结果后生成回答 ← **主要消耗** |
| Position 4-5 | deepseek-v4-flash | 11-2/108 | avg ~18K | 后续轮次（多次工具调用累积） |

- 35 traces 无 tool 调用（纯对话）：deepseek 输入仅 ~2,750-3,000 tokens
- 72 traces 有 tool 调用：deepseek 输入 avg ~18,604 tokens

### 10.2 响应调用的上下文构成（有工具调用的 72 个 traces）

| 内容来源 | Token 数 | 占比 |
|---------|---------|------|
| System Prompt | ~100 | 0.5% |
| User Query + Tool Rules | ~350 | 1.9% |
| Tool Usage Warnings | ~600 | 3.2% |
| **★ Tool 返回结果（搜索结果）** | **~15,600** | **83.8%** |
| Assistant 历史消息 | ~200 | 1.1% |
| **合计** | **~18,600** | **100%** |

> **工具返回结果占总上下文的 84%，是上下文膨胀的唯一根因。**

### 10.3 工具返回结果详情（tavily_web_search）

- **来源**：tavily MCP 搜索工具
- **触发率**：72/108 (67%) 的请求会调用搜索
- **每次搜索返回**：
  - 6-24 个搜索结果（平均 ~10 个）
  - 每个结果 2K-5K chars（800-2K tokens）
  - 包含：标题 + URL + 相关性分数 + 1-5 个网页摘录段落
  - 总计：43K-88K chars → 约 15K-35K tokens

**具体例子：**

| 查询 | 结果数 | 总字符数 | 估算 tokens |
|------|-------|---------|------------|
| "今日AI新闻" | 20 | 43,334 | ~15K |
| "Ngrok隧道原理" | 7 | 44,538 | ~17K |
| "深圳小众游玩" | 24 | 88,568 | ~35K |

**存在的问题：**

1. 结果数过多：6-24 个，实际只需 3-5 个高相关的
2. 内容冗余：同一 URL 不同语言版本同时返回
3. 无压缩：原始搜索结果直接灌入 LLM，无摘要/截断
4. 多轮累积：3 次工具调用后，上下文可达 60K tokens

---

## 11. 优化措施

### 11.1 tavily_web_search 参数优化（已实施）

**文件**: `backend/app/mcp/mcp_servers/tavily_mcp/server.py`

| 参数 | 修改前 | 修改后 | 预期效果 |
|------|-------|-------|---------|
| `queries` 描述 | "推荐使用 2-3 个查询" | "简单问题使用 1 个 query，复杂/多角度问题使用 2-3 个查询" | avg 2.8 → ~1.5 个 query |
| `result_per_query` 默认值 | 10 | 5 | 每个 query 结果数减半 |
| `chunks_per_source` 默认值 | 3 | 2 | 每个结果摘录段减半 |

**预期 Token 减少**：约 70-80%

```
修改前（单次搜索）:
  10 results × 3 chunks × ~800 tokens ≈ 24K tokens

修改后（单次搜索）:
  5 results × 2 chunks × ~800 tokens ≈ 8K tokens

综合（含 query 数减少）:
  修改前: 2.8 queries × 24K ≈ 67K tokens
  修改后: 1.5 queries × 8K ≈ 12K tokens
  减少: ~82%
```

### 11.2 待进一步优化

| 方向 | 优先级 | 说明 |
|------|-------|------|
| Tool result 去重 | 🟠 高 | 同一 URL 不同语言版本只保留 1 个 |
| Tool result 截断 | 🟠 高 | 每个结果只保留标题 + 最相关的 1 个内容段落 |
| Tool usage warning 精简 | 🟡 中 | 当前 ~600 tokens 的警告文本可精简到 ~100 tokens |
| 减少工具调用触发率 | 🟡 中 | 优化决策 prompt，当前 67% 触发率可降到 ~50% |
| tavily 超时控制 | 🟡 中 | tavily_web_search 平均 7.6s，最大 34.4s |
| code_execute 预热 | 🟢 低 | code_execute_code 平均 10s，最大 22.5s |
| memory-search 异步化 | 🟢 低 | 当前 ~660ms，影响不大 |

---

*报告生成时间: 2026-06-21*
