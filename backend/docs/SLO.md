# SLO / 错误预算规则（导入现有 Prometheus 平台）

**最后核对**：2026-08-21

本仓库**不**内嵌 Prometheus / Alertmanager。规则 YAML 放在 [`deploy/prometheus/`](../../deploy/prometheus/)，由运维导入现有 Prometheus 平台。

应用侧提供：

- `GET /metrics`：HTTP 默认指标 + 进程指标 + 健康探活 Gauge（见 [PROMETHEUS_METRICS.md](./PROMETHEUS_METRICS.md)）
- `GET /api/health/live` / `ready` / ``：探活并更新 `health_dependency_up` 等

## 1. 默认 SLO

面向内部 Agent 系统：上游 LLM、MCP 工具等外部依赖多，可用性目标取 **99.5%**（相对 99.9% 更宽松，避免外部抖动过度烧预算）。

| 项 | 值 |
|----|-----|
| 目标 | 月 HTTP 可用性 **99.5%** |
| 错误预算 | 约 **216 分钟** downtime / 30 天 |
| SLI | 非 5xx 请求占比（排除 `/metrics` 与 `/api/health*`） |

剩余错误预算（recording 名 `slo:http_error_budget:remaining_30d`）：

- `1` = 预算未消耗
- `0` = 预算耗尽
- 负值 = 已超 SLO

Grafana 可查：`slo:http_error_budget:remaining_30d`，或换算剩余分钟：

```promql
slo:http_error_budget:remaining_30d * 216
```

## 2. 导入步骤

1. 确认平台已 scrape 后端 `/metrics`（job 名以平台为准，下文示例用 `chat-agent-backend`）。
2. 打开 [`deploy/prometheus/recording_rules.yml`](../../deploy/prometheus/recording_rules.yml) 与 [`alerting_rules.yml`](../../deploy/prometheus/alerting_rules.yml)。
3. 按实际 job / instance label **改写**规则中的 `job="chat-agent-backend"`（若平台无此 label，可删掉 job 选择器，仅保留 handler 过滤）。
4. 核对 Instrumentator 暴露的 handler 标签实际取值：

```bash
curl -s http://localhost:8000/metrics | rg 'http_requests_total|http_request_duration'
```

部分版本用 `handler`，也可能是 `path` 或模板路径（如 `/api/chat/...`）。延迟告警里的 handler 选择器需与线上一致。

5. 将 YAML 粘贴/上传到 Prometheus 平台的 recording / alerting 配置，reload 后验证：

```promql
slo:http_availability:ratio_5m
slo:http_error_budget:remaining_30d
```

## 3. 告警摘要

| 告警 | 严重级别 | 含义 |
|------|----------|------|
| `ChatAgentErrorBudgetBurnCritical` | critical | 1h 快速烧预算且 5m 仍在烧 |
| `ChatAgentErrorBudgetBurnWarning` | warning | 6h 中速烧预算且 30m 仍在烧 |
| `ChatAgentDependencyDown` | critical | postgres/redis 探活失败持续 2m |
| `ChatAgentLLMUnreachable` | warning | llm 探活失败持续 5m |
| `ChatAgentDBPoolNearExhaustion` | warning | 连接池占用 > 90% 持续 5m |
| `ChatAgentChatLatencyHigh` | warning | 聊天相关 handler p95 > 10s |

多窗口 burn rate 避免短暂抖动误报。阈值与阈值可按业务改。

## 4. 探活与 SLO 的分工

| 机制 | 回答的问题 |
|------|------------|
| `/api/health/live` | 进程是否还活着（编排 liveness） |
| `/api/health/ready` | 硬依赖（DB/Redis）是否可接流量 |
| `/api/health` | 深度诊断（含 LLM、连接池） |
| Prometheus SLO | 过去一段时间可用性与错误预算还剩多少 |

LLM **不**进入 ready：上游挂了重启本进程无效，由 `ChatAgentLLMUnreachable` 告警。
