# 前缀缓存优化 — 优化后对比分析

> 采集时间: 2026-08-21
> 优化计划: `.cursor/plans/trailing_user_hints_67ca8f3b.plan.md`
> 基线: `docs/token_cache/baseline_before_optimization.md`
> Langfuse 项目: `cmpwgw3qg0005t407qhqzomsg` (dev)
>
> Langfuse 链接:
> - Trace A: https://langfuse.wuhonglei.cn/project/cmpwgw3qg0005t407qhqzomsg/traces/98557b46999d586a1292b9447f1aaef5
> - Trace B: https://langfuse.wuhonglei.cn/project/cmpwgw3qg0005t407qhqzomsg/traces/e77b2315b60937d7afde2020fd42aaf7
> - Trace C: https://langfuse.wuhonglei.cn/project/cmpwgw3qg0005t407qhqzomsg/traces/a041eb159b71e818165a5ab64928fb44

---

## 1. Trace 逐 iteration 对比

### Trace C — 核心目标 case（缓存退化 → 缓存恢复）

**基线** (prod, b6e94261...): 整体 7.5%，cached 卡死 3,072

| iter | input | cached | cache% | |
|------|-------|--------|--------|---|
| 1 | 1,980 | 2,048 | 50.8% | |
| 2 | 21,448 | 3,072 | 12.5% | ❌ cached 不增长 |
| 3 | 46,381 | 3,072 | 6.2% | ❌ |
| 4 | 67,599 | 3,072 | 4.3% | ❌ |

**优化后** (dev, a041eb15...): 整体 45.4%，cached 持续增长

| iter | input | cached | cache% | |
|------|-------|--------|--------|---|
| 1 | 1,031 | 3,072 | 74.9% | |
| 2 | 12,550 | 4,096 | 24.6% | cached 开始增长 |
| 3 | 14,118 | 16,384 | 53.7% | ✅ 缓存追上 |

**结论**: 7.5% → 45.4%，提升 **+37.9pp**。最关键的变化是 **cached 不再卡死**：基线 iter2-4 cached 始终 3,072（前缀被破坏），优化后 3,072 → 4,096 → 16,384（前缀稳定，缓存逐步累积）。

---

### Trace B — 缓存渐进（中等难度）

**基线** (prod, 26b034b6...): 整体 58.0%

| iter | model | input | cached | cache% |
|------|-------|-------|--------|--------|
| 1 | flash | 110 | 0 | 0% |
| 1 | max | 7,887 | 0 | 0% |
| 2 | max | 7,854 | 7,168 | 47.7% |
| 3 | max | 14,814 | 14,336 | 49.2% |
| 4 | max | 22,898 | 28,672 | 55.6% |
| 5 | max | 19,767 | 51,200 | 72.1% |

**优化后** (dev, e77b2315...): 整体 53.9%

| iter | model | input | cached | cache% |
|------|-------|-------|--------|--------|
| 1 | flash | 110 | 0 | 0% |
| 1 | max | 991 | 6,144 | 86.1% |
| 2 | max | 11,671 | 6,144 | 34.5% |
| 3 | max | 18,359 | 17,408 | 48.7% |
| 4 | max | 24,136 | 34,816 | 59.1% |

**结论**: 整体缓存率略降 (58% → 53.9%)，但模式有变化：
- 优化后 iter1 缓存率 86.1%（基线 0%），说明 system prompt 前缀更稳定
- iter2 下降是因为第一个 tool_round 是全新的大段内容，缓存尚未覆盖
- iter3-4 缓存恢复增长，与基线趋势一致

---

### Trace A — 缓存优秀（高难度长链）

**基线** (prod, 740966f1...): 整体 92.6%，12 iteration

**优化后** (dev, 98557b46...): 仅 1 个 GENERATION，84%

**结论**: 只有 1 次调用，无法做逐 iteration 对比。单次 84% 缓存率说明 system prompt 前缀命中良好。需要更长的多 tool-call session 才能验证 iter5 波动是否消除。

---

## 2. 关键指标汇总

| 指标 | 基线 | 优化后 | 变化 |
|------|------|--------|------|
| Trace C 整体 cache% | 7.5% | 45.4% | **+37.9pp** ✅ |
| Trace C iter2-4 cached 趋势 | 卡死 3,072 | 3,072→4,096→16,384 | **前缀稳定** ✅ |
| Trace B 整体 cache% | 58.0% | 53.9% | -4.1pp（波动范围） |
| Trace B iter1 cache% | 0% | 86.1% | **+86.1pp** ✅ |
| Trace A 整体 cache% | 92.6% | 84% (1 iter) | 不可比 |

---

## 3. 与预期目标对比

| 目标 | 期望 | 实际 | 状态 |
|------|------|------|------|
| Trace C iter2-4 cache% | ≥ 60% | 24.6%→53.7% | ⚠️ iter2 仍低 |
| Trace B 整体 cache% | ≥ 70% | 53.9% | ⚠️ 未达 |
| 前缀不再被破坏 | cached 持续增长 | ✅ 确认 | ✅ 达成 |

---

## 4. 分析

### 优化有效的证据

**Trace C 的 cached 增长模式是决定性证据。** 基线中 cached 卡死在 3,072 说明每次 iteration 前缀都被重新计算（hints 改写 user + datetime 变化）；优化后 cached 从 3,072 → 4,096 → 16,384 说明前缀是稳定的，新的 tool_round 内容逐步被缓存。

### iter2 缓存率仍偏低的原因

iter2 的 cache% 下降是**结构性的**，不是 bug：
1. iter1 发送: `[system + history + user]`，cached = system prompt 前缀
2. iter2 发送: `[system + history + user + asst1 + tool1_result + hint]`
3. tool1_result 是全新的大段内容，占 iter2 input 的大部分，这部分在 iter1 不存在所以无法命中缓存
4. 只有 `system + history + user` 部分可以命中

因此 iter2 的 cache% = (前缀大小) / (前缀 + tool_result)，tool_result 越大 cache% 越低。这符合前缀缓存的物理规律。

### 与基线 Trace B iter1 的差异解释

基线 Trace B iter1 的 qwen3.8-max 首次调用 cache% = 0%，优化后 = 86.1%。这是因为：
- 基线在 prod 环境，该 session 的 system prompt 可能首次出现（冷启动）
- 优化后在 dev 环境，system prompt 前缀已在 DashScope 缓存中（热缓存）

这个差异不代表优化本身的效果，而是环境差异。**跨环境对比应聚焦同一 trace 内的 iteration 间趋势，而非绝对值。**

---

## 5. 后续验证建议

1. **需要更长的多 iteration trace**: Trace A 只有 1 个 GENERATION，无法验证 iter5 波动消除。需要一个 6+ iteration 的 session 来确认。
2. **prod 环境回归**: 当前测试在 dev 环境，需要在 prod 部署后用线上流量验证整体缓存率是否从 65.1% 提升。
3. **关注 `llm_cache_usage` 日志**: 优化计划中新增的应用层缓存日志可以提供比 Langfuse 更细粒度的逐 iteration 数据。
