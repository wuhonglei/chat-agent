# Prometheus 指标（当前实现）

**最后核对**：2026-08-21

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

workers 数：`WORKERS=$(( $(nproc) * 2 ))`。启动命令**不使用** `--preload`：

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

## 6. 源码索引

| 主题 | 路径 |
|------|------|
| multiproc 目录初始化、Instrumentator、collector 启动 | `app/main.py` |
| 自定义进程指标 | `app/core/process_metrics.py` |
| 健康探活指标 | `app/core/health_metrics.py` |
| 探活逻辑 | `app/core/health_probes.py` |
| 健康检查路由 | `app/api/health.py` |
| 生产启动与目录清理 | `start.sh` |
| SLO / 告警规则（导入现有 Prometheus 平台） | `deploy/prometheus/`、`backend/docs/SLO.md` |
