# Prometheus 指标（当前实现）

**最后核对**：2026-09-13

本文档说明后端如何暴露 Prometheus 指标、多进程（Gunicorn）模式下的目录约定，以及自定义进程 CPU/内存指标。

## 1. 暴露方式

应用在 `app/main.py` 中：

1. **在 import `prometheus_client` 之前**设置 `PROMETHEUS_MULTIPROC_DIR`（未设置时默认 `{tempdir}/prometheus_multiproc` 并创建目录）；
2. 使用 `prometheus_fastapi_instrumentator.Instrumentator().instrument(app).expose(app)` 暴露 **`GET /metrics`**；
3. 调用 `start_process_metrics_collector()` 启动后台线程，周期性写入自定义进程 Gauge。

开发模式（`make dev` / 单进程 uvicorn）与生产 Gunicorn 多 worker 均可抓取 `/metrics`。多 worker 时必须使用 multiprocess 目录，否则进程级指标会不准或冲突。

## 2. 生产启动约定

`backend/start.sh` 在启动 Gunicorn 前：

```bash
export PROMETHEUS_MULTIPROC_DIR=/tmp/prometheus_multiproc
rm -rf "$PROMETHEUS_MULTIPROC_DIR"
mkdir -p "$PROMETHEUS_MULTIPROC_DIR"
```

workers 数：`WORKERS=$(nproc)`（等于 CPU 核数，不再 `* 2`，以降低常驻内存）。启动命令**不使用** `--preload`：

```bash
gunicorn app.main:app -w $WORKERS -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

原因：Nacos 使用 gRPC 客户端；master `--preload` 后再 fork worker 会导致 gRPC 线程状态不一致并触发 **SIGSEGV**。因此每个 worker 独立加载 `app.main`，并在进程内自行初始化 `PROMETHEUS_MULTIPROC_DIR` 与指标注册表。

约束：

- 每次进程组启动应清空 multiproc 目录，避免遗留 `.db` 文件污染聚合；
- 不要在多个无关进程组之间共享同一 `PROMETHEUS_MULTIPROC_DIR`；
- scrape `/metrics` 时由 multiprocess collector 聚合各 worker 写入的文件；
- **不要**为「优化冷启动」擅自加回 `--preload`，除非已验证 Nacos/gRPC 在 fork 后安全。

## 3. 自定义进程指标

默认的 `process_resident_memory_bytes` / `process_cpu_seconds_total` 在 multiprocess 模式下不会被正确聚合。项目用 `psutil` 另写带 `pid` label 的 Gauge：

| 指标名 | 类型 | 标签 | 含义 |
|--------|------|------|------|
| `process_resident_memory_bytes_custom` | Gauge | `pid` | 当前 worker RSS（字节） |
| `process_cpu_seconds_total_custom` | Gauge | `pid` | 用户+系统 CPU 累计秒数 |

实现：`app/core/process_metrics.py`。后台守护线程默认每 **5 秒**采集一次（`start_process_metrics_collector(interval=5.0)`）。

## 4. 抓取与排障

```bash
# 本地单进程
curl -s http://localhost:8000/metrics | head

# 确认自定义指标
curl -s http://localhost:8000/metrics | rg 'process_resident_memory_bytes_custom|process_cpu_seconds_total_custom'
```

常见问题：

1. **`/metrics` 404**：确认 `Instrumentator().expose(app)` 已执行，且反向代理未剥离该路径。
2. **多 worker 指标重复/缺失**：检查启动日志中的 `Prometheus multiproc dir`，以及环境变量是否在 import app 前生效。
3. **自定义 Gauge 为 0 或不更新**：进程可能无 `psutil` 权限（`AccessDenied` 时静默跳过）；确认 collector 线程已启动。
4. **容器重启后脏数据**：确认 `start.sh` 在启动前 `rm -rf` multiproc 目录。

## 5. 健康探活指标

由 `/api/health/ready` 与 `/api/health` 在探活时顺带写入（不另开采集线程）。多 worker 下带 `pid` label，与进程指标一致；scrape 时由 multiprocess collector 聚合。

| 指标名 | 类型 | 标签 | 含义 |
|--------|------|------|------|
| `health_dependency_up` | Gauge | `component`, `pid` | 依赖探活是否成功（1/0）；`component` 为 `postgres` / `redis` / `llm` |
| `health_probe_latency_seconds` | Gauge | `component`, `pid` | 最近一次探活耗时（秒） |
| `db_pool_size` | Gauge | `pid` | 本 worker SQLAlchemy `pool_size` |
| `db_pool_checked_out` | Gauge | `pid` | 本 worker 已借出连接数 |
| `db_pool_overflow` | Gauge | `pid` | 本 worker overflow 连接数 |

实现：`app/core/health_metrics.py`，由 `app/core/health_probes.py` 调用。

HTTP 请求计数与延迟仍使用 `prometheus_fastapi_instrumentator` 默认指标（如 `http_requests_total`、`http_request_duration_seconds`）。SLO / 错误预算 recording 与 alerting 规则见仓库根目录 `deploy/prometheus/` 与 `docs/SLO.md`（`backend/docs/SLO.md`）。

## 6. 常驻 worker 指标（`eval_worker` / `memory_worker`）

这两个 worker 与 backend 同镜像、不同 command（`uv run python -m eval_worker.main` /
`memory_worker.main`），**没有常驻 HTTP 端口**：指标由 `prometheus_client` 用独立
registry 另起一个监听暴露，端口来自各自配置的 `metrics_port`（evaluator 默认 `9465`、
memory-governance 默认 `9464`，`0` = 关闭），compose 里已发布到宿主机供内网抓取。

共用骨架 `app/core/worker_metrics.py`，每个 worker 的映射在 `eval_worker/metrics.py`
与 `memory_worker/metrics.py`，指标名以 worker 前缀区分：

| 指标（`{prefix}_…`） | 类型 | 标签 | 含义 |
|--------|------|------|------|
| `{prefix}_enabled` | Gauge | — | 配置是否启用（1/0），用于抑制「主动关闭」时的告警 |
| `{prefix}_runs_total` | Counter | `mode`, `result` | 运行次数；`result` ∈ `ok` / `failed` / `disabled` / `not_configured` / `unsupported` |
| `{prefix}_last_success_timestamp_seconds` | Gauge | `mode` | **心跳**：最近一次成功运行的 Unix 时间戳 |
| `{prefix}_run_duration_seconds` | Gauge | `mode` | 最近一次运行耗时 |
| `{prefix}_units_total` | Counter | `mode`, `outcome` | 处理单元数（治理=用户 `scanned/succeeded/skipped/failed`；评估=`traces/sampled/judge_success/judge_failed/low_score`） |

`prefix` 分别为 `memory_governance`、`evaluator`；`mode` 为 `daily` / `sweep`
（评估 worker 固定 `scheduled`）。另有 `memory_governance_sweep_enabled`。

语义约定（与 HTTP 指标不同，排查时按这个顺序看）：

1. **只有 `result="ok"` 推进心跳**——「配置缺失 / 后端不支持 / 主动关闭」只计数，
   不伪装成健康；`enabled`/`sweep_enabled` 为 0 时才抑制 staleness 告警。
2. 进程启动时把心跳写成**启动时间**，给新部署一个调度周期内的宽限期；「跑了但一直失败」
   由 `result="failed"` 覆盖；「反复重启」不在心跳覆盖范围内，由 `up{}` 或容器级
   （cadvisor）指标覆盖。
3. 单元计数**只在非 0 时建序列**，所以别写 `increase(...{outcome="x"}) == 0`
   （序列不存在 → 空向量 → 规则永不触发），用 `unless` 表达「没有成功」。
4. 不用 multiprocess 模式：worker 是单进程，沿用 backend 的 `PROMETHEUS_MULTIPROC_DIR`
   反而会把指标混进 backend 的聚合目录。

告警规则见 `deploy/prometheus/alerting_rules.yml` 的 `chat_agent_worker_alerts` 组，
抓取配置片段见 `deploy/prometheus/scrape-config.snippet.yml`，任务编排细节见
[MEMORY_GOVERNANCE_WORKER.md](./MEMORY_GOVERNANCE_WORKER.md)。

## 7. 源码索引

| 主题 | 路径 |
|------|------|
| multiproc 目录初始化、Instrumentator、collector 启动 | `app/main.py` |
| 自定义进程指标 | `app/core/process_metrics.py` |
| 健康探活指标 | `app/core/health_metrics.py` |
| 探活逻辑 | `app/core/health_probes.py` |
| 健康检查路由 | `app/api/health.py` |
| worker 指标骨架（心跳 / 运行结局 / 监听） | `app/core/worker_metrics.py` |
| 记忆治理 worker 埋点 | `memory_worker/metrics.py`、`memory_worker/main.py` |
| 评估 worker 埋点 | `eval_worker/metrics.py`、`eval_worker/main.py` |
| 生产启动与目录清理 | `start.sh` |
| SLO / 告警规则（导入现有 Prometheus 平台） | `deploy/prometheus/`、`backend/docs/SLO.md` |
