# Langfuse 线上缓存命中率报告

> 数据来源: langfuse.wuhonglei.cn | 项目: cmpwh4pcg0002qn07mv4f20af | 环境: prod  
> 统计范围: 近 30 天 (2026-07-22 ~ 2026-08-21)  
> 数据源: ClickHouse `events_full` 表，`provided_usage_details` 字段  
> 生成时间: 2026-08-21

---

## 整体概览

| 指标 | 值 |
|------|-----|
| 总调用次数 (GENERATION) | 466 |
| 命中缓存次数 | 250 (53.6%) |
| 未命中缓存次数 | 216 (46.4%) |
| 总 input tokens (非缓存部分) | 2,119,785 |
| 缓存 tokens | 3,945,856 |
| 有效 input 总量 | 6,065,641 |
| **token 级缓存率** | **65.1%** |
| 总 output tokens | 236,973 |

> **token 级缓存率** = 缓存 tokens / (非缓存 input + 缓存 tokens)，反映整体 token 级别的缓存复用比例。

---

## 按模型拆分

| 模型 | 调用数 | 命中次数 | 调用级命中率 | token 缓存率 |
|------|--------|----------|-------------|-------------|
| qwen3.8-max | 345 | 249 | 72.2% | 65.7% |
| qwen3.5-flash | 76 | 0 | 0% | 0% |
| qwen3.7-flash | 41 | 0 | 0% | 0% |
| kimi-k3 | 3 | 0 | 0% | 0% |
| deepseek-v4-flash | 1 | 1 | 100% | 85.3% |

---

## 每日趋势

| 日期 | 调用数 | 命中数 | 缓存率 | 缓存 tokens |
|------|--------|--------|--------|------------|
| 08-06 | 95 | 47 | 49.5% | 115,968 |
| 08-07 | 48 | 29 | 60.4% | 136,064 |
| 08-08 | 45 | 21 | 46.7% | 62,592 |
| 08-09 | 13 | 6 | 46.2% | 16,512 |
| 08-10 | 18 | 9 | 50.0% | 44,288 |
| 08-11 | 79 | 55 | 69.6% | 3,041,280 |
| 08-12 | 45 | 19 | 42.2% | 115,712 |
| 08-13 | 30 | 17 | 56.7% | 158,848 |
| 08-14 | 10 | 2 | 20.0% | 5,120 |
| 08-15 | 2 | 0 | 0% | 0 |
| 08-19 | 19 | 14 | 73.7% | 54,528 |
| 08-20 | 48 | 27 | 56.2% | 180,480 |
| 08-21 | 14 | 4 | 28.6% | 14,464 |

> 8/11 日缓存率最高 (69.6%)，当天缓存 tokens 高达 300 万，说明存在大量相似前缀的批量调用。

---

## 关键发现

1. **缓存仅发生在 qwen3.8-max 和 deepseek-v4-flash 上**。qwen3.5-flash / qwen3.7-flash / kimi-k3 完全无缓存命中。

2. **qwen3.8-max 作为主力模型** (占 74% 调用)，调用级命中率 72.2%，说明约 3/4 的请求复用了前缀缓存。token 级缓存率 65.7%，意味着平均每请求有 65% 的 input token 走了缓存。

3. **qwen3.5-flash 和 qwen3.7-flash 无缓存**，可能原因：
   - 这些模型的请求 prompt 前缀不稳定（含时间戳/随机数等）
   - DashScope 对这些模型未启用 KV Cache
   - 请求量太小或调用间隔过长导致缓存过期

4. **成本细节未配置**（`provided_cost_details` 为空），无法量化缓存节省的费用。

---

## 建议

- **qwen3.8-max**: 72% 缓存率已经不错，继续稳定 system prompt 前缀即可
- **qwen3.5-flash / qwen3.7-flash**: 如需缓存收益，检查是否启用了 DashScope 的 Context Cache 功能（部分模型需手动开启）
- **配置模型单价**: 在 Langfuse 中配置模型单价以跟踪缓存节省的实际费用

---

## 查询方法

数据从 ClickHouse `events_full` 表提取，使用 `provided_usage_details` Map 字段：

```sql
-- 关键字段
provided_usage_details['input']              -- 非缓存 input tokens
provided_usage_details['input_cached_tokens'] -- 缓存 input tokens
provided_usage_details['output']             -- output tokens
provided_usage_details['total']              -- 总 tokens

-- 整体缓存率
SELECT 
  countIf(provided_usage_details['input_cached_tokens'] > 0) / count() as gen_cache_rate,
  sum(provided_usage_details['input_cached_tokens']) / 
  (sum(provided_usage_details['input']) + sum(provided_usage_details['input_cached_tokens'])) as token_cache_rate
FROM events_full
WHERE project_id = 'cmpwh4pcg0002qn07mv4f20af'
  AND type = 'GENERATION'
  AND start_time >= now() - INTERVAL 30 DAY;
```
