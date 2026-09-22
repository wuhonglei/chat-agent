# 监控接入手册（deploy/prometheus）

**最后核对**：2026-09-22（核对方式：直接 SSH 到两台机器，用 Prometheus / Alertmanager / Loki
的 HTTP API 实测，不看文档推断）

本仓库**不**内嵌 Prometheus / Grafana / Alertmanager，只提供规则与抓取配置，实际平台在：

| 机器 | 角色 | 相关组件 |
|------|------|----------|
| `1.12.53.9`（公共服务机） | 监控平台 | `prometheus`（:9090）、`alertmanager`（新增，:9093）、`loki-loki-1`（:3100）、`loki-grafana-1`（:3000） |
| `134.175.182.235`（应用机） | 被监控方 | `chat-agent-*` 容器、`node-exporter`（新增，:9100）、`chat-agent-promtail` |

Prometheus 容器配置：宿主机 `/root/prometheus/prometheus.yml` → 容器
`/etc/prometheus/prometheus.yml`；规则目录 `/root/prometheus/rules/` → `/etc/prometheus/rules/`。
容器带 `--web.enable-lifecycle`，改完配置可以热加载：

```bash
sudo docker exec prometheus promtool check config /etc/prometheus/prometheus.yml   # 校验
curl -X POST http://127.0.0.1:9090/-/reload                                       # 热加载
sudo docker restart prometheus                                                    # 兜底
```

## 1. 线上现状（2026-09-22 改动前后对比，均为实测）

| 项 | 改动前 | 改动后 |
|----|--------|--------|
| scrape job | 1 个（`chat-agent` → `10.0.24.3:8000`） | 4 个（+`chat-agent-memory-governance`:9464、+`chat-agent-evaluator`:9465、+`node`:9100） |
| 已加载规则 | **0 组**（`/api/v1/rules` 空，规则文件从没导入过） | **4 组 / 25 条**（slo 告警 6 + worker 告警 8 + 容器告警 5 + slo 记录 6），0 条评估报错 |
| 告警出口 | **无 Alertmanager**（`activeAlertmanagers: []`，规则响了也没人收到） | Alertmanager 0.34.1，邮件出口 `smtp.qq.com:587`，实测投递成功 |
| 主机/容器指标 | `node_*` / `container_*` **全部无数据** | `node_*` 有（node-exporter :9100）；容器指标走 `docker_container_*`（textfile collector） |
| 日志采集 | Loki `container` 标签只有 backend / frontend / postgres | 增加 memory-governance / evaluator / sites，共 6 个 |
| 规则里的 job 名 | 文件里写 `chat-agent-backend`，真实 job 是 `chat-agent` → **所有规则查不到数据** | 全部对齐为 `chat-agent`（`recording_rules.yml` 11 处、`alerting_rules.yml` 7 处） |

## 2. 仍然缺的（需要你操作或等部署）

1. **安全组放行（唯一的硬阻塞）**：从服务机到应用机，`8000` / `5432` 通，**`9100` / `9464` / `9465`
   被挡住**（应用机本地 `ufw inactive`、宿主 iptables 只有 YunJing 的源 IP 黑名单，不是主机侧拦截，
   应用机上这些端口本地 curl 都是 200）。
   需要在腾讯云控制台给**应用机**安全组加规则：来源 = 服务机内网 IP，端口 `9100`、`9464`、`9465`。
   放行前 `node` / 两个 worker job 的 target 一定是 down——这是预期，不是配置写错。
2. **应用侧新版本部署**：9464/9465 的指标要等本仓库包含 `metrics_port` 的版本（含
   `backend/app/core/worker_metrics.py`）部署到应用机之后才有数据；当前线上还是老镜像，
   `docker ps` 里两个 worker 只暴露 `8000/tcp`。
3. **可选**：给 `sites`（nginx 静态网关）加 blackbox 探活（现在没有 `probe_success`）；注意
   无 Host 的请求会打到 default_server 返回 404，探针要带 Host 头。
4. **可选**：Grafana `FastAPI Observability` 变量 `app_name` 保存的默认值是空串（必须靠 URL 传
   `chat-agent`），建议在面板设置里把默认值改掉。

## 3. 文件清单

| 文件 | 用到哪里 | 说明 |
|------|----------|------|
| `recording_rules.yml` | Prometheus rule_files | HTTP 可用性 SLI / 错误预算（99.5%） |
| `alerting_rules.yml` | Prometheus rule_files | `chat_agent_slo_alerts`（错误预算、依赖、DB 池、chat p95）+ `chat_agent_worker_alerts`（memory-governance / evaluator 心跳、失败、空转） |
| `container_alerting_rules.yml` | Prometheus rule_files | 容器/主机级：重启、容器不在、内存逼近 limit、ClickHouse 高 CPU、根分区余量 |
| `scrape-config.snippet.yml` | Prometheus 主配置 | 线上 `prometheus.yml` 的完整内容（4 个 job + rule_files + alerting） |
| `promtail-jobs.snippet.yaml` | 应用机 promtail 配置 | 补齐 memory-governance / evaluator / sites 的日志采集（**已合并**） |
| `../monitoring/collect_container_metrics.py` | 应用机 cron | 容器指标（cadvisor 在本机不可用，见 `../monitoring/README.md`） |

## 4. 本次实际执行的操作（可复现）

```bash
# —— 应用机 134.175.182.235 ——
# 1) 日志采集：合并 promtail-jobs.snippet.yaml 到
#    /home/ubuntu/promtail/config/promtail-config.yaml（备份 .bak.<ts>），重启 promtail
# 2) 主机+容器指标：起 node-exporter(:9100)，cron 每分钟跑 collect_container_metrics.py
# 3) 让 health_dependency_up / db_pool_* 有数据：cron 每分钟 curl /api/health/ready

# —— 服务机 1.12.53.9 ——
# 4) 规则文件入 /root/prometheus/rules/，prometheus.yml 补 rule_files + alerting + 新 job
#    （备份 /root/prometheus/prometheus.yml.bak.<ts>），重建 prometheus 容器（沿用 TSDB 卷）
# 5) Alertmanager 容器：配置 /root/alertmanager/alertmanager.yml（0600，由应用机
#    webhooks/.env 的 SMTP 生成），--user 0 运行（镜像默认非 root，读不了 0600 文件）
#    -p 172.17.0.1:9093:9093 —— 只发布在 docker0 网关，不对外网暴露
```

## 5. 校验命令（照着跑一遍就是一次体检）

```bash
# targets 健康度
curl -s localhost:9090/api/v1/targets | python3 -m json.tool | grep -E '"job"|health'
# 规则条数与评估错误
curl -s localhost:9090/api/v1/rules | python3 -c "import json,sys; d=json.load(sys.stdin)['data']['groups']; print(sum(len(g['rules']) for g in d),'rules'); print([r['name'] for g in d for r in g['rules'] if r.get('health')!='ok'])"
# 告警出口是否挂上
curl -s localhost:9090/api/v1/alertmanagers
# 邮件出口自检（会真的发一封邮件）
curl -s -X POST http://172.17.0.1:9093/api/v2/alerts -H 'Content-Type: application/json' \
  -d '[{"labels":{"alertname":"SelfTest","severity":"critical","service":"chat-agent"},"annotations":{"summary":"自检"}}]'
curl -s http://172.17.0.1:9093/metrics | grep -E 'notifications_total|notifications_failed_total.+(email)'
# 容器指标（应用机，本地）
curl -s http://127.0.0.1:9100/metrics | grep '^docker_container_up'
```

规则文件里的 PromQL 也可以直接对着线上 Prometheus 逐条查（`GET /api/v1/query?query=<expr>`），
比本地装 promtool 快；改动规则后先 `promtool check rules` 再热加载。
