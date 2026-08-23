# 上下文压缩效果验证 — 线上 Trace 采样

> 数据来源: Langfuse prod (langfuse.wuhonglei.cn)
> 查询时间: 2026-08-23
> 项目: cmpwh4pcg0002qn07mv4f20af
> 数据总量: 525 traces, 128 sessions

## 压缩信号说明

当前线上仅 **2 条 trace** 的 LLM input 中包含 `<window_out_summary>` 压缩标记，均来自同一 session `01a02939-4ed1-770e-8f87-5db30e36b660`。其余 trace 均未触发压缩。

上下文压缩由 `ContextSummaryService` 在会话级实现：当窗口外消息过多时，旧消息被 LLM 摘要并注入 system prompt 的 `<tool_call_context><window_out_summary>` 标签中。压缩状态存储在 PostgreSQL `conversation_contexts` 表，不直接体现在单条 trace 的 observation 中。

---

## 场景1: 多轮工具调用（≥3 轮工具）— 6 条

| # | trace_id | session | tools | gens | input_chars | tokens_in | max_tool_out | 工具类型 |
|---|----------|---------|-------|------|-------------|-----------|-------------|---------|
| 1 | `7cfb7dca971d925a` | 01a02c84 | 15 | 11 | 1,397,558 | 55,244 | 23,184 | tavily + zread + file |
| 2 | `740966f1cf672a99` | 019fefbd | 11 | 12 | 8,206,016 | 114,418 | 12,513 | tavily + shell + file |
| 3 | `26b034b679646682` | 019ffb5d | 4 | 6 | 708,828 | 73,330 | 79,807 | file_read_file ×4 |
| 4 | `b6e942616ec2fe95` | 019fdffb | 3 | 5 | 926,455 | 138,064 | 29,320 | tavily_web_search ×3 |
| 5 | `20360e8a4a640f75` | 019fef84 | 3 | 4 | 362,488 | 8,981 | 42,908 | tavily extract + search |
| 6 | `b2b8aeb251a9a087` | 019fe53c | 3 | 4 | 66,302 | 3,869 | 186 | weather + time |

**Langfuse 链接:**
1. https://langfuse.wuhonglei.cn/project/cmpwh4pcg0002qn07mv4f20af/traces/7cfb7dca971d925a35c3526785fa4b6e
2. https://langfuse.wuhonglei.cn/project/cmpwh4pcg0002qn07mv4f20af/traces/740966f1cf672a993f663dc06c5ba3ba
3. https://langfuse.wuhonglei.cn/project/cmpwh4pcg0002qn07mv4f20af/traces/26b034b67964668296506b114e627264
4. https://langfuse.wuhonglei.cn/project/cmpwh4pcg0002qn07mv4f20af/traces/b6e942616ec2fe95bf21da5ffb851bc0
5. https://langfuse.wuhonglei.cn/project/cmpwh4pcg0002qn07mv4f20af/traces/20360e8a4a640f75aeb0496d3f29fb84
6. https://langfuse.wuhonglei.cn/project/cmpwh4pcg0002qn07mv4f20af/traces/b2b8aeb251a9a0878bfb48e433f5cc41

---

## 场景2: 长对话（≥10 条消息/会话）— 5 条

选取 5 个长会话的 **最后一条 trace**（此时累积消息最多，压缩效果最显著）。

| # | trace_id | session | session_gens | trace_in_chars | tokens_in | max_gen_input |
|---|----------|---------|-------------|----------------|-----------|---------------|
| 1 | `a5c16632f2d2e9a6` | 019fefbd | 36 | 3,930,349 | 239,002 | 228,727 |
| 2 | `5af81a5efcf74770` | 019fef84 | 13 | 216,521 | 2,532 | 1,646 |
| 3 | `44a65af49114b202` | 019fdd33 | 13 | 88,084 | 2,665 | 2,665 |
| 4 | `d55f200ae7d26fcb` | 01a01df0 | 11 | 50,895 | 1,930 | 1,930 |
| 5 | `43d013ed7937575c` | 01a01a30 | 11 | 50,867 | 1,733 | 1,733 |

**Langfuse 链接:**
1. https://langfuse.wuhonglei.cn/project/cmpwh4pcg0002qn07mv4f20af/traces/a5c16632f2d2e9a6497a3cdd87763d6e
2. https://langfuse.wuhonglei.cn/project/cmpwh4pcg0002qn07mv4f20af/traces/5af81a5efcf747706a819a11588009e1
3. https://langfuse.wuhonglei.cn/project/cmpwh4pcg0002qn07mv4f20af/traces/44a65af49114b20253c5b6c671b19fbd
4. https://langfuse.wuhonglei.cn/project/cmpwh4pcg0002qn07mv4f20af/traces/d55f200ae7d26fcb380cfd6db04ddb7d
5. https://langfuse.wuhonglei.cn/project/cmpwh4pcg0002qn07mv4f20af/traces/43d013ed7937575c8e10cb6c1f47c4be

---

## 场景3: 大工具结果（单条 >8K 字符）— 5 条

| # | trace_id | session | tool_name | max_output_chars | tokens_in | total_in_chars |
|---|----------|---------|-----------|-----------------|-----------|----------------|
| 1 | `d519471d25e92830` | 019fefbd | file_read_file | 103,519 | 93,184 | 745,117 |
| 2 | `130b2d3ca5dd3fd2` | 019fefbd | file_read_file | 103,519 | 117,425 | 4,458,082 |
| 3 | `b4fe08de9b862cc3` | 019fef84 | tavily_web_search | 61,767 | 8,189 | 213,209 |
| 4 | `98d8a81a253a46f9` | 019fd63c | tavily_web_search | 51,205 | 31,509 | 250,382 |
| 5 | `6bb3969967c2bb93` | 019ff4a8 | file_read_file | 48,975 | 23,014 | 124,866 |

**Langfuse 链接:**
1. https://langfuse.wuhonglei.cn/project/cmpwh4pcg0002qn07mv4f20af/traces/d519471d25e92830826c49a5634d26ae
2. https://langfuse.wuhonglei.cn/project/cmpwh4pcg0002qn07mv4f20af/traces/130b2d3ca5dd3fd21ed33db30d0ec3f8
3. https://langfuse.wuhonglei.cn/project/cmpwh4pcg0002qn07mv4f20af/traces/b4fe08de9b862cc383cf734ce91b1767
4. https://langfuse.wuhonglei.cn/project/cmpwh4pcg0002qn07mv4f20af/traces/98d8a81a253a46f9920e3ebfc80fff90
5. https://langfuse.wuhonglei.cn/project/cmpwh4pcg0002qn07mv4f20af/traces/6bb3969967c2bb939fd450753dc2df4d

---

## 场景4: 未触发压缩（对照组）— 4 条

选取 1-2 工具、2 代际、中等 input 的简单对话。

| # | trace_id | session | tools | gens | input_chars | tokens_in | max_gen_input |
|---|----------|---------|-------|------|-------------|-----------|---------------|
| 1 | `db0ebb3fc7670861` | 019fefbd | 1 | 2 | 147,419 | 5,556 | 4,179 |
| 2 | `80d32819a77ff958` | 01a01cff | 1 | 2 | 142,434 | 8,177 | 5,447 |
| 3 | `a9f6edd0880f8dd0` | 019ffb57 | 1 | 2 | 138,654 | 9,743 | 8,013 |
| 4 | `57a7367ddc53d3b0` | 019fefbd | 1 | 2 | 112,997 | 5,004 | 3,706 |

**Langfuse 链接:**
1. https://langfuse.wuhonglei.cn/project/cmpwh4pcg0002qn07mv4f20af/traces/db0ebb3fc767086157e804e90ed3b927
2. https://langfuse.wuhonglei.cn/project/cmpwh4pcg0002qn07mv4f20af/traces/80d32819a77ff958ce0673824e953c16
3. https://langfuse.wuhonglei.cn/project/cmpwh4pcg0002qn07mv4f20af/traces/a9f6edd0880f8dd07dc774e0ac765408
4. https://langfuse.wuhonglei.cn/project/cmpwh4pcg0002qn07mv4f20af/traces/57a7367ddc53d3b07c8815247267f63a

---

## 观察与注意事项

1. **压缩触发率极低**: 525 条 trace 中仅 2 条含 `<window_out_summary>`，说明当前线上大部分对话轮次不多，未达到压缩阈值。
2. **长对话 session 累积效应明显**: session `019fefbd` 有 36 代际、12 trace，最后一条 trace 的 max_gen_input 达 228,727 tokens，说明历史消息确实在累积。
3. **工具结果是主要 token 消耗源**: file_read_file 和 tavily_web_search 的输出可达 100K+ 字符，这些大结果在后续轮次会作为上下文反复传入。
4. **对照组特征**: 1-2 工具 + 2 代际的简单对话，input 在 100-150K chars，tokens_in 约 5K-10K，属于正常范围。
5. **压缩验证建议**: 要对比压缩效果，需要从 PostgreSQL `conversation_contexts` 表查询 `summary_before_window` 非空的 session，然后对比压缩前后的 token 变化。
