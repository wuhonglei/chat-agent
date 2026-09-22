# 监控接入手册（deploy/prometheus）

**最后核对**：2026-09-22（核对方式：经 Grafana 已登录会话查 Prometheus `/api/v1/status/config`、
`/api/v1/rules`、`/api/v1/alertmanagers` 与 Loki 标签）

本仓库**不**内嵌 Prometheus / Grafana / Alertmanager，只提供规则与抓取片段，由运维导入现有平台。
本文记录**线上现状**与**还差什么**，细节见 `backend/docs/PROMETHEUS_METRICS.md`、
`backend/docs/SLO.md`。

## 1. 线上现状（实测）

Prometheus（Grafana 数据源 `cft5k6h0yx69sd` → `http://172.19.0.1:9090`）：

| 项 | 现状 |
|----|------|
| scrape job | **只有 1 个**：`chat-agent` → `10.0.24.3:8000/metrics`（15s，up=1） |
| 已加载规则 | **0 组**：`/api/v1/rules` 返回空 —— `alerting_rules.yml` / `recording_rules.yml` 都没导入 |
| Alertmanager | **没有**：`/api/v1/alertmanagers` 的 `activeAlertmanagers` 为空，规则触发了也没人收到 |
| 指标家族 | `container_*` / `node_*` / `probe_success` **全部无数据**（没有 cadvisor / node-exporter / blackbox） |
| 缺失埋点 | `memory_governance_*`、`evaluator_*` 无数据（本次已在应用侧补齐，等抓取配置） |

Grafana 面板：`FastAPI Observability`（HTTP 指标 + 进程指标，13 面板；变量 `app_name`
保存的默认值是空串，靠 URL 传 `chat-agent`）、`Chat Agent Logs`（5 面板，全部
`container="chat-agent-backend"`）。

Loki（`http://loki:3100`，由宿主机 `chat-agent-promtail` 推送）：`container` 标签只有
`chat-agent-backend` / `chat-agent-frontend` / `chat-agent-postgres`；
**memory-governance / evaluator / sites 的日志没有进 Loki**（promtail 一个容器一个 job，
没声明这三个）。

## 2. 待办清单（按优先级）

1. **接上告警出口**：导入规则文件（下面第 3 节）并配 Alertmanager，或在 Grafana 用
   unified alerting 托管。没有这一步，后面所有规则都是死的。
   - 规则文件顶部注释里的 `job="chat-agent-backend"` 需要与真实 job 名对齐（现在是
     `chat-agent`，历史文件写的是 `chat-agent-backend`）。
2. **补抓取目标**：`scrape-config.snippet.yml` 里的两个 worker job（9464 / 9465），
   需要本仓库已部署包含 `metrics_port` 的新版本。
3. **补日志采集**：`promtail-jobs.snippet.yaml` 合并进宿主机
   `/home/ubuntu/promtail/config/promtail-config.yaml`（注意：该目录里的 `config.yml`
   是**未被加载**的旧文件，promtail 实际用 `-config.file=/etc/promtail/config.yaml`），
   然后重启 promtail。
4. **补容器/主机指标**：宿主机部署 cadvisor + node-exporter，导入
   `container_alerting_rules.yml`。这是覆盖面最大的一步——今天（2026-09-22）
   `chat-agent-memory-governance` 因镜像漏 COPY 启动即崩、restart 循环 16 次，
   全程无人知晓，就是因为没有任何容器级指标。
5. **可选**：给 `sites`（nginx 静态网关）加 blackbox 探活（现在没有 `probe_success`）；
   注意它无 Host 的请求会打到 default_server 返回 404，探针要带 Host 头。

## 3. 文件清单

| 文件 | 导入到 | 说明 |
|------|--------|------|
| `recording_rules.yml` | Prometheus rule_files | HTTP 可用性 SLI / 错误预算（99.5%） |
| `alerting_rules.yml` | Prometheus rule_files | 组 `chat_agent_slo_alerts`（错误预算、依赖、DB 池、chat p95）+ 组 `chat_agent_worker_alerts`（判 2026-09-22 新增：memory-governance / evaluator 的心跳、失败、空转） |
| `container_alerting_rules.yml` | Prometheus rule_files | 容器/主机级（需 cadvisor + node-exporter，当前未部署） |
| `scrape-config.snippet.yml` | Prometheus scrape_configs | 三个 job：backend / memory-governance / evaluator |
| `promtail-jobs.snippet.yaml` | 宿主机 promtail 配置 | 补齐 memory-governance / evaluator / sites 的日志采集 |

## 4. 校验方式

规则文件里的 PromQL 可以对着线上 Prometheus 逐条查（只读）确认语法与语义，
例如 `GET /api/v1/query?query=<expr>`；本地没有 promtool 时这条路最快。
worker 指标发布后可先手工确认：

```bash
# 宿主机上直接看 worker 指标（端口在 compose 里发布）
curl -s http://127.0.0.1:9464/metrics | rg 'memory_governance_(enabled|runs_total|last_success)'
curl -s http://127.0.0.1:9465/metrics | rg 'evaluator_(enabled|runs_total|last_success)'
```
