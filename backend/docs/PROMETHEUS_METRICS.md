# Prometheus 指标（当前实现）

**最后核对**：2026-07-26

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

并以 `--preload` 启动，确保 master 预加载 app、指标注册表在 fork 前初始化：

```bash
gunicorn app.main:app -w $WORKERS -k uvicorn.workers.UvicornWorker --preload --bind 0.0.0.0:8000
```

约束：

- 每次进程组启动应清空 multiproc 目录，避免遗留 `.db` 文件污染聚合；
- 不要在多个无关进程组之间共享同一 `PROMETHEUS_MULTIPROC_DIR`；
- scrape `/metrics` 时由 multiprocess collector 聚合各 worker 写入的文件。

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

## 5. 源码索引

| 主题 | 路径 |
|------|------|
| multiproc 目录初始化、Instrumentator、collector 启动 | `app/main.py` |
| 自定义进程指标 | `app/core/process_metrics.py` |
| 生产启动与目录清理 | `start.sh` |
