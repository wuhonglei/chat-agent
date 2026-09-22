# 应用机（134.175.182.235）主机/容器指标采集

**部署日期**：2026-09-22　**覆盖**：node-exporter（主机指标）+ textfile collector（容器指标）

## 1. 为什么不用 cadvisor

cadvisor 是这类需求的默认答案，但在这台机器上**拿不到任何按容器的指标**，实测结论：

- 机器是 Ubuntu / kernel 6.8 / cgroup v2 + containerd；
- `gcr.io/cadvisor/cadvisor` 在境内**不可达**，Docker Hub 上能拉的只有 `zcube/cadvisor`
  （`v0.45.0-dirty`，2022 年）；
- 跑起来后 `docker logs cadvisor` 持续刷
  `failed getting container info for "/system.slice/docker-<id>.scope": unknown container`；
- `/metrics` 里 `container_*` 系列**没有任何 `name` 标签**（`grep -c 'name="'` = 0），
  只有 `id="/"`、`id="/YunJing"` 这种 cgroup 级序列 → 按容器的告警一条都写不出来；
- `zcube/cadvisor:v0.49.1`、`registry.aliyuncs.com/google_containers/cadvisor:v0.49.1`
  都拉不到（试过，全 FAIL）。

所以容器指标改用 **node-exporter textfile collector + 每分钟一次 docker CLI 采集**，
无外部镜像依赖、逻辑可读、出问题能自己查。

## 2. 部署形态

```bash
# 主机 + 容器指标（应用机）
docker run -d --name node-exporter --restart unless-stopped \
  -p 9100:9100 \
  -v /proc:/host/proc:ro -v /sys:/host/sys:ro -v /:/rootfs:ro,rslave \
  -v /home/ubuntu/monitoring/textfile:/var/lib/node_exporter/textfile:ro \
  prom/node-exporter:latest \
  --path.procfs=/host/proc --path.sysfs=/host/sys --path.rootfs=/rootfs \
  --collector.textfile.directory=/var/lib/node_exporter/textfile \
  '--collector.filesystem.mount-points-exclude=^/(dev|proc|sys|var/lib/docker/.+)($|/)'

# 每分钟生成容器指标（cron）
* * * * * /home/ubuntu/monitoring/collect_container_metrics.py >/dev/null 2>&1

# 让 health_dependency_up / db_pool_* 有数据（否则依赖类告警永远不触发，见下）
* * * * * curl -s -m 10 -o /dev/null http://127.0.0.1:8000/api/health/ready
```

脚本落位：`/home/ubuntu/monitoring/collect_container_metrics.py`（本目录的文件原样拷过去，
`chmod +x`）。输出 `/home/ubuntu/monitoring/textfile/chat_agent_containers.prom`，
写成 `0644`（**必须**：node-exporter 容器以非 root 运行，读不了 0600）。

## 3. 暴露的指标

| 指标 | 含义 | 来源 |
|------|------|------|
| `docker_container_up{name}` | 1 = 在跑，0 = 停了/**被删了** | `docker inspect` + 期望容器清单 |
| `docker_container_restart_count{name}` | 累计重启次数 | `docker inspect .RestartCount` |
| `docker_container_start_time_seconds{name}` | 最近一次启动时间 | `docker inspect .State.StartedAt` |
| `docker_container_memory_working_set_bytes{name}` | 内存占用 | `docker stats` |
| `docker_container_memory_limit_bytes{name}` | 内存上限（0 = 未限制） | `docker inspect .HostConfig.Memory` |
| `docker_container_cpu_percent{name}` | CPU 百分比（瞬时） | `docker stats` |

**「容器消失」为什么要单独写 up=0**：指标序列一旦消失，Prometheus 就再也看不到它，
`absent()` 也只能对「已知名字」写；所以采集脚本对 `EXPECTED_CONTAINERS`（默认
`chat-agent-backend/frontend/postgres/evaluator/memory-governance/sites/promtail`，
可用环境变量覆盖）里查不到的容器显式写 `up 0`，`ChatAgentContainerDown` 才成立。
换了 service 名记得同步这个清单。

告警规则见 `../prometheus/container_alerting_rules.yml`（`docker_container_*` + `node_filesystem_*`）。

## 4. 连带的两个坑（都已处理，别改回去）

- **`health_dependency_up` / `db_pool_*` 只在被人请求时才写入**：它们由
  `backend/app/core/health_probes.py` 在 `/api/health/ready`、`/api/health` 被调用时
  更新（`health_metrics.py` 里只是注册了 Gauge）。线上此前没有任何东西调这个端点，
  所以 `/metrics` 里这两族指标**一条都没有**，`alerting_rules.yml` 里依赖它们的
  3 条告警（依赖宕 / LLM 不可达 / DB 池接近耗尽）永远是「不会触发」而不是「没触发」。
  → 加了上面那行 cron。删掉它 = 这 3 条告警静默复活成死规则。
- **node-exporter 的 textfile 目录必须可读**：`prom/node-exporter` 镜像以非 root 运行，
  脚本里 `os.chmod(tmp, 0o644)` 之后再 `os.replace`，目录 755。

## 5. 自检

```bash
curl -s http://127.0.0.1:9100/metrics | grep -E '^docker_container_(up|restart_count)' | head
curl -s http://127.0.0.1:9100/metrics | grep -E '^node_textfile_(mtime_seconds|scrape_error)'
ls -l /home/ubuntu/monitoring/textfile/          # mtime 应该是 1 分钟内
crontab -l | grep monitoring                      # 两行 cron 都在
```
