# 前缀缓存优化 — 线上基线快照

> 采集时间: 2026-08-21  
> 优化计划: `.cursor/plans/prefix_cache_optimization_3e2c3e8a.plan.md`  
> 目的: 在实施 hints 尾部追加 + datetime 冻结之前，锁定线上基线数据，优化后同批 trace 对比回归

---

## 1. 整体基线（30 天汇总）

| 指标 | 值 |
|------|-----|
| 总 GENERATION 调用 | 466 |
| 命中缓存 (cached > 0) | 250 (53.6%) |
| token 级缓存率 | 65.1% |
| 主力模型 qwen3.8-max 调用级命中率 | 72.2% |
| qwen3.5-flash / qwen3.7-flash 命中率 | 0% |

详见: `docs/token_cache/2026-08-21_cache_hit_report.md`

---

## 2. 重点跟踪 Trace（优化后用同模型同用户回放对比）

选取标准: 多 iteration tool-call（≥3 次 GENERATION），覆盖「好 / 中 / 差」三种缓存模式。

### Trace A — 缓存优秀（12 iteration, qwen3.8-max）

- trace_id: `740966f1cf672a993f663dc06c5ba3ba`
- session: `019fefbd-2249-7f66-bee4-d351a622a2c7`
- 时间: 2026-08-11 08:49:17 ~ 08:53:03
- 整体缓存率: 92.6%

| iter | input | cached | cache% | 备注 |
|------|-------|--------|--------|------|
| 1 | 90,437 | 27,648 | 23.4% | 首次调用，部分命中 |
| 2 | 1,733 | 117,760 | 98.5% | 前缀几乎全命中 |
| 3 | 859 | 118,784 | 99.3% | ↑ |
| 4 | 1,014 | 118,784 | 99.2% | |
| 5 | 7,445 | 119,296 | 94.1% | hints 改写 user 导致略降? |
| 6 | 2,112 | 125,952 | 98.4% | |
| 7 | 5,014 | 128,000 | 96.2% | |
| 8 | 1,296 | 132,096 | 99.0% | |
| 9 | 812 | 133,120 | 99.4% | |
| 10 | 1,152 | 133,120 | 99.1% | |
| 11 | 302 | 134,144 | 99.8% | |
| 12 | 2,242 | 134,144 | 98.4% | |

**观察**: iter 5 出现 cache% 下降 (94.1%)，可能是 hints 就地改写 user 导致前缀短时断裂。优化后应消除此波动。

### Trace B — 缓存渐进（6 iteration, qwen3.7-flash → qwen3.8-max）

- trace_id: `26b034b67964668296506b114e627264`
- session: `019ffb5d-4457-745b-88a7-9b9761671365`
- 时间: 2026-08-13 13:49:52 ~ 13:50:02
- 整体缓存率: 58.0%

| iter | model | input | cached | cache% | 备注 |
|------|-------|-------|--------|--------|------|
| 1 | qwen3.7-flash | 110 | 0 | 0% | flash 无缓存 |
| 1 | qwen3.8-max | 7,887 | 0 | 0% | 首次并行调用 |
| 2 | qwen3.8-max | 7,854 | 7,168 | 47.7% | |
| 3 | qwen3.8-max | 14,814 | 14,336 | 49.2% | |
| 4 | qwen3.8-max | 22,898 | 28,672 | 55.6% | |
| 5 | qwen3.8-max | 19,767 | 51,200 | 72.1% | |

**观察**: qwen3.7-flash 始终 0%；qwen3.8-max 逐轮上升但没到 90%+，说明前缀在缓慢扩展（hints 改写可能在稀释命中比例）。

### Trace C — 缓存退化（5 iteration, qwen3.5-flash → qwen3.8-max）

- trace_id: `b6e942616ec2fe95bf21da5ffb851bc0`
- session: `019fdffb-8a3e-7b1d-9834-fea88cd798a2`
- 时间: 2026-08-08 06:07:19 ~ 06:12:26
- 整体缓存率: 7.5%

| iter | model | input | cached | cache% | 备注 |
|------|-------|-------|--------|--------|------|
| 1 | qwen3.5-flash | 656 | 0 | 0% | flash 无缓存 |
| 1 | qwen3.8-max | 1,980 | 2,048 | 50.8% | |
| 2 | qwen3.8-max | 21,448 | 3,072 | 12.5% | ❌ 缓存骤降 |
| 3 | qwen3.8-max | 46,381 | 3,072 | 6.2% | ❌ 持续退化 |
| 4 | qwen3.8-max | 67,599 | 3,072 | 4.3% | ❌ 几乎无缓存 |

**观察**: 这是典型的「前缀被破坏」模式 — input 持续增长但 cached 几乎不动。很可能 hints 就地改写 user message + datetime 每次变化导致整个前缀重算。**这是本次优化的核心目标 case。** 优化后 cached 应随 input 同步增长，cache% 稳定在 60%+。

---

## 3. 优化后对比维度

对上述 3 个 trace，用相同 session + 相似 query 回放后，比较:

| 维度 | 基线 | 优化后期望 |
|------|------|-----------|
| Trace C iter2-4 cache% | 12% → 6% → 4% | ≥ 60% 稳定 |
| Trace A iter5 cache% 波动 | 94% (vs 前后 99%) | 消除波动，稳定 99%+ |
| Trace B 整体 cache% | 58% | ≥ 70% |
| 整体 30 天 token 缓存率 | 65.1% | ≥ 75% |
| 应用层 llm_cache_usage 日志 | 无 | 有，含 cache_hit_tokens |

---

## 4. 回放方法

```bash
# 方案 A: 手动在 chat-agent 前端用相似 query 触发多 tool-call 场景
# 方案 B: 用 eval replay 脚本 + Langfuse 对比

# 优化后查询同维度数据:
AUTH=$(echo -n 'pk-lf-***:sk-lf-***' | base64)
curl -s "http://134.175.182.235:18123/" --data-binary "
SELECT trace_id, span_id,
  provided_usage_details['input'] as input,
  provided_usage_details['input_cached_tokens'] as cached,
  round(provided_usage_details['input_cached_tokens'] / (provided_usage_details['input'] + provided_usage_details['input_cached_tokens'] + 1e-9) * 100, 1) as cache_pct
FROM events_full
WHERE project_id = 'cmpwh4pcg0002qn07mv4f20af' AND type = 'GENERATION'
  AND trace_id = '<新 trace_id>'
ORDER BY start_time
FORMAT TabSeparated
" -u clickhouse:WgSfbDYzuOcRxCtWrC52
```
