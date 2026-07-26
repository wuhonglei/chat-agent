# LLM 重试与熔断（当前实现）

**最后核对**：2026-07-26

本文档说明 `LLMService.call_llm_api` 在建连阶段的错误分类、指数退避重试与按 `api_base` 的进程级熔断。面向排查「偶发 429/503」「整站 LLM 暂时不可用」的开发与运维同学。

## 1. 范围与边界

| 覆盖 | 不覆盖 |
|------|--------|
| `chat.completions.create` 建连阶段失败 | 已拿到 stream 后的 chunk 消费失败 |
| 可重试的 transient/busy（含超时、连接错误、408/429/5xx 等） | 配额/鉴权类错误的重试 |
| 按 `api_base` 共享的进程内熔断器 | 跨 worker / 跨进程的分布式熔断 |
| 用户可读中文 `LLMCallError` | SSE 专用 `llm_retry` 事件（当前未实现；重试对用户静默） |

源码：

- `app/services/base_service/llm_error_handling.py`
- `app/services/base_service/llm_service.py`（`call_llm_api`）
- 配置：`settings.llm_reliability` → `LLMReliabilityConfig`

## 2. 调用流程

```text
call_llm_api
  → breaker.is_open()? 是 → 立即抛 circuit_open
  → 循环最多 retry_max_attempts：
       create(...) 成功 → record_success，返回
       CancelledError → release_probe，再抛出
       其它异常 → classify_error
         可重试且未达上限 → sleep(backoff) 再试（不记熔断失败）
         否则 → transient/busy 记 record_failure；其它 release_probe
                → 抛 LLMCallError
```

要点：

- **流式任务**：只有建连失败会重试；中途断流不在此模块重试。
- **熔断计数**：仅最终失败且 reason 为 `transient`/`busy` 时 `record_failure`；中间成功重试前的失败不累计。
- **探针**：half-open 只允许一个飞行中请求；取消时 `release_probe` 避免卡死。

## 3. 错误分类

`classify_error(exc) -> (retriable, reason)`：

| reason | 可重试 | 典型信号 |
|--------|:------:|----------|
| `quota` | 否 | insufficient_quota、billing、余额不足… |
| `auth` | 否 | unauthorized、invalid api key、无权… |
| `transient` | 是 | `APITimeoutError`/`APIConnectionError`/`StreamChunkTimeoutError` 等；HTTP 408/409/425/429/500/502/503/504 |
| `busy` | 是 | server busy、rate limit、服务繁忙… |
| `generic` | 否 | 其它 |
| `circuit_open` | 否 | 熔断打开时直接构造，不经过 classify |

用户文案由 `user_message_for` 生成，例如熔断：「LLM 服务连续失败，已暂时熔断保护，请稍后再试。」

## 4. 退避策略

`build_retry_delay_ms(attempt, exc, base, cap)`：

1. 优先响应头 `Retry-After-Ms` / `Retry-After`（秒或 HTTP-date）；
2. 否则 `base_delay_ms * 2^(attempt-1)`，封顶 `retry_cap_delay_ms`。

## 5. 熔断器状态

`CircuitBreaker`：closed → open → half-open（单探针）→ closed。

| 配置 | 默认 | 说明 |
|------|-----:|------|
| `circuit_failure_threshold` | `5` | 连续 transient/busy **最终失败** 次数后打开 |
| `circuit_recovery_timeout_sec` | `30` | 打开后冷却秒数，到期进入 half-open |

熔断器表按 `api_base` 缓存在进程内（`get_circuit_breaker`）。多 worker 时各自独立，不共享。

## 6. 配置

```dotenv
LLM_RELIABILITY__RETRY_MAX_ATTEMPTS=3
LLM_RELIABILITY__RETRY_BASE_DELAY_MS=1000
LLM_RELIABILITY__RETRY_CAP_DELAY_MS=8000
LLM_RELIABILITY__CIRCUIT_FAILURE_THRESHOLD=5
LLM_RELIABILITY__CIRCUIT_RECOVERY_TIMEOUT_SEC=30
```

| 字段 | 默认 | 说明 |
|------|-----:|------|
| `retry_max_attempts` | `3` | 含首次的最大尝试次数 |
| `retry_base_delay_ms` | `1000` | 指数退避基础延迟 |
| `retry_cap_delay_ms` | `8000` | 退避上限 |
| `circuit_failure_threshold` | `5` | 打开熔断的连续失败阈值 |
| `circuit_recovery_timeout_sec` | `30` | 冷却时间 |

## 7. 排障

1. 日志：`Transient LLM error; retrying`（含 `attempt`/`wait_ms`/`reason`）；熔断相关 `LLM circuit breaker tripped/reset/probe failed`。
2. 用户侧突然大面积「已暂时熔断」：某 `api_base` 连续失败达阈值；等冷却或重启该 worker；同时查上游 429/5xx。
3. 鉴权/配额错误不会重试也不会记入熔断；应查 API Key 与账单。
4. 流式中途失败：不在本模块处理，查 SSE/chunk 超时与网络。
5. 单测可调用 `reset_circuit_breakers_for_tests()` 清空进程表。

## 8. 单测

`tests/services/test_llm_error_handling.py` 覆盖分类、退避、熔断与 `call_llm_api` 重试路径。
