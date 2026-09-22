# 记忆治理 Worker（Mem0 Dream pass 定时触发）

对「每天整理记忆」的落地实现：独立 Worker 进程按用户 fan-out 调用 Mem0 的
`POST {chat_context.memory_config.base_url}/dream`，把 merge / supersede / synthesis
交给 Mem0 的 governance 引擎执行。

- 代码入口：`backend/memory_worker/main.py`、`app/services/memory_governance/`
- Compose 服务：`docker-compose.yml` 的 `memory-governance`
- Mem0 侧实现：`mem0/server/routers/dream.py`、`mem0/server/governance/engine.py`
- 默认行为：`enabled=true`；日跑 04:00 治理「近 30 天有聊天记录」的用户，
  周扫（周日 04:00）补治理「有记忆但近期没聊天」的沉睡用户

## 为什么独立部署，不复用 evaluator

`docker-compose.yml` 里已有的 `evaluator` 只跑 `eval_worker.main`（Langfuse 采样 +
裁判打分的批量评估），与记忆治理是两件事：

| 差异 | evaluator | memory-governance |
|------|-----------|-------------------|
| 领域 | 评估（读 Langfuse Trace、写 bad case） | 记忆治理（调 Mem0 Dream pass） |
| 调度单元 | 全局一次，产出一条 `eval_run_log` | 按 `user_id` fan-out，一个用户一次 pass |
| 资源峰值 | 裁判并发（`judge_concurrency`） | LLM 全量 consolidate/synthesis，易吃内存 |
| 依赖 | Langfuse + 裁判模型 | Mem0 REST + 用户表 |

共用容器会让「治理 OOM」和「当天评估」互相拖累，且部署范围（`webhooks/main.py`
按变更路径判定）会把两边耦合在一起。因此本 Worker 与 evaluator 同镜像、不同
`command`，独立限额与 cron。

## 触发链路

```
APScheduler(CronTrigger, Asia/Shanghai)
  ├─ job: memory_governance_daily（schedule_cron，默认 0 4 * * *）
  └─ job: memory_governance_sweep（sweep_cron，默认 0 4 * * sun）
       └─ memory_worker.main → run_scheduled_governance(mode)
            └─ MemoryGovernanceService.run(mode)
                 ├─ collect_user_ids()
                 │    daily: select_chat_active_users(session, cfg)   # conversations 表选人
                 │    sweep: collect_sweep_users()                    # Mem0 admin 列表发现
                 ├─ asyncio.Semaphore(concurrency)                    # 并发调用
                 ├─ 闸门：watermark → min_memories                    # 跳过则 status=skipped
                 └─ DreamClient.run_pass(user_id=…)
                      POST {base_url}/dream  {"user_id","consolidate","synthesize","force"}
                      headers: X-API-Key / Authorization: Token 前缀 + API Key
            └─ 汇总 DreamRunReport → 结构化日志
```

闸门用到的读接口（都走同一个 `base_url` 与鉴权）：

| 用途 | 请求 | 说明 |
|------|------|------|
| pass 水位 | `GET /dream?user_id=<id>&source=manual,scheduler&limit=1` | 服务端按 `source` 过滤 + `created_at` 倒序，`limit=1` 即**最近一次全量 pass** 的 `created_at`；客户端仍逐行核对 `source`（失败方向安全：宁可放行多花一次 pass，也不把 on_add 当已治理而永久跳过）。读失败/为空/全是 on_add 则不拦截 |
| 最小记忆量 | `GET /memories?user_id=<id>&page=1&page_size=1` | 读响应里的 `count`（admin 分页语义），拿不到则不拦截 |
| 周扫候选 | `GET /memories?page=<n>&page_size=1000`（不带标识符） | admin 全量列表，提取 `user_id`；分页上限 1000 |

Mem0 一次 pass 的审计（`pass_id` / `stats` / `actions`）由 Mem0 侧的
`dream_passes` / `dream_actions` 表承担，本 Worker 只做编排与汇总，不重复落库。

## 选人规则（重要）

两层口径，日跑 + 周扫：

1. **日跑按聊天活跃度**（唯一信号，无配置开关）：
   `select user_id from conversations group by user_id having max(last_message_created_at) >= now() - interval 'N days'`
   —— 语义是「近 N 天真实产生过记忆写入的用户」。这条 SQL 正好走现成复合索引
   `ix_conversations_user_active_last_msg (user_id, is_active, desc(last_message_created_at))`
   （`app/models/conversation_db.py:15-22`）；排序为最后消息时间倒序，截断到
   `max_users_per_run`。
2. **周扫补长尾**（`sweep_cron`，周日 04:00）：从 Mem0 的 admin 记忆列表发现「有记忆但
   近期没聊天」的用户，让沉睡用户的存量碎片一周收一次，不会永久漏掉。
3. **水位去重**（`skip_if_governed=true`）：跳过「**最近一次全量 pass** 时间 ≥ 该用户最后一条
   消息时间」的用户——没有新记忆写入就不重跑全量 pass。周扫用户没有可靠的最后活动时间，
   退化用 `min_pass_interval_days`（默认 7 天）兜底。
   - 「全量 pass」= `POST /dream` 落库的记录（默认 `source="manual"`，本 Worker 传
     `source="scheduler"`；mem0 侧 `normalize_pass_source` 做小写/限长归一）；
     **`source="on_add"` 的轻量 consolidate 不算**（只 merge/supersede，不做 synthesis）。
     写记忆触发的 on_add 时间戳总是最新，若把它当水位，活跃用户会被
     永久跳过（实测 dev：两位用户的历史 pass 全是/大多是 on_add，其中一位累计 733 条记忆）；
     只认 `manual` 也不行——本 Worker 自己跑的 pass 会被自己无视，每次都被判定「没治理过」。
   - 只取 `limit=1` 就够了：服务端已按 `source` 过滤并按 `created_at` 倒序，第一行就是最近一次
     全量 pass（此前要多拉 200 行回来本地筛，是因为过滤能力还没上线）。客户端仍逐行核对
     `source`，但那不是为兼容旧服务，而是**失败方向安全**：万一拿到 on_add（服务端异常/代理
     吞掉参数），宁可返回 `None` 放行（多花一次 pass 的钱），也不要把 on_add 认成「已治理」
     而永久跳过该用户。扫不到 → `None` → 不拦截。
4. **最小记忆量门槛**（`min_memories`，默认 10）：`count` 低于阈值直接跳过；
   为 3 条记忆跑全量 consolidate + synthesis 是纯浪费。读数拿不到（None）时不拦截，
   避免因 Mem0 波动误伤。

为什么不用登录时间 / `users.status` 作信号（曾被实现过，已移除）：

- 登录 ≈ 会话续期，记忆变化 ≈ 聊天轮次，两者不对齐。
- JWT 寿命 **35 天**（`app/core/jwt.py:85-87`：`exp = now + 35 * 24 * 3600`）比 30 天
  窗口还长 → 一直在用旧 token 聊天的活跃用户会被移出治理窗口，越活跃越先掉出。
- `users.last_login_at` 只在登录时写，且按它排序会让「刚登录、还没聊天」的人占满
  `max_users_per_run` 名额。
- `users.status` 是登录会话标志——登录置 `active`，登出即置 `inactive`
  （`app/services/user/user_db.py:136`）。拿它当「活跃用户」判据会把已登出的活跃用户
  全部漏掉（本地库实测：3 个用户全是 `inactive`）。
- `activity_within_days=0` 表示不按活跃度过滤（全部用户）。

## 配置项（`memory_governance_worker.*`）

| 字段 | 默认 | 说明 |
|------|------|------|
| `enabled` | `true` | 总开关；关闭时调度器仍启动但跳过任务 |
| `schedule_cron` | `0 4 * * *` | 日跑 cron（5 段），时区 Asia/Shanghai |
| `sweep_enabled` | `true` | 是否启用周扫 |
| `sweep_cron` | `0 4 * * sun` | 周扫 cron。**用 `sun` 而不是 `0`**：APScheduler 的 `day_of_week` 是 0=周一，与 POSIX cron 的 0=周日不同 |
| `sweep_page_size` | `1000` | 周扫发现用户时的 Mem0 分页大小（Mem0 上限 1000） |
| `sweep_max_pages` | `50` | 周扫最多翻多少页（防御性上限） |
| `run_on_startup` | `false` | 启动即跑一次日跑（联调用） |
| `consolidate` | `true` | 传给 Mem0：执行 merge/supersede |
| `synthesize` | `true` | 传给 Mem0：执行模式记忆提炼 |
| `force` | `false` | 绕过 synthesis 的最小记忆条数阈值（Mem0 默认 20 条） |
| `activity_within_days` | `30` | 日跑活跃窗口（天），信号为 conversations 最后消息时间；0=不过滤 |
| `min_memories` | `10` | 记忆数低于该值的用户跳过；0=不启用该门槛 |
| `skip_if_governed` | `true` | 水位去重：上次 pass 不早于最后一条消息则跳过 |
| `min_pass_interval_days` | `7` | 周扫用户的水位兜底间隔（天，0=不启用） |
| `max_users_per_run` | `500` | 单次运行用户数上限（日跑与周扫共用） |
| `concurrency` | `2` | 并发调用 Mem0 的用户数（1-16） |
| `request_timeout_s` | `300` | 单用户 pass 的 HTTP 超时（秒） |
| `retry_attempts` | `2` | 单用户失败后的总尝试次数（1-5） |
| `retry_backoff_s` | `5` | 退避基数（秒，指数增长） |
| `metrics_port` | `9464` | Prometheus 指标监听端口（宿主发布 `9464:9464`）；`0`=关闭 |

环境变量写法（`__` 嵌套分隔符）：

```bash
MEMORY_GOVERNANCE_WORKER__ENABLED=true
MEMORY_GOVERNANCE_WORKER__SCHEDULE_CRON="0 4 * * *"
MEMORY_GOVERNANCE_WORKER__SWEEP_CRON="0 4 * * sun"
MEMORY_GOVERNANCE_WORKER__MIN_MEMORIES=10
MEMORY_GOVERNANCE_WORKER__CONCURRENCY=2
```

运行报告（`DreamRunReport`）字段：`mode`（daily/sweep）、`scanned_users`、`skip_reason`
（整轮被跳过的原因：`disabled` / `not_configured` / `platform`；`None` = 这轮真的跑了）、
`succeeded`、`skipped`、`failed`、`failures`；每个用户一条 `UserDreamOutcome`，含
`status`（ok/skipped/failed）、`reason`（跳过原因，如 `governed_after_last_message`、
`below_min_memories:3<10`）、`attempts`、`pass_id`、`stats`。

## 指标与告警

worker 没有常驻 HTTP 端口，指标由 `prometheus_client` 另起一个监听暴露（默认 `9464`，
compose 里发布 `9464:9464`），埋点在 `memory_worker/metrics.py` + 共用骨架
`app/core/worker_metrics.py`：

| 指标 | 类型 | 说明 |
|------|------|------|
| `memory_governance_enabled` | gauge | 配置是否启用（抑制「主动关闭」时的告警） |
| `memory_governance_sweep_enabled` | gauge | 周扫是否启用 |
| `memory_governance_runs_total{mode,result}` | counter | 每次运行的结局：`ok` / `failed` / `disabled` / `not_configured` / `unsupported` |
| `memory_governance_last_success_timestamp_seconds{mode}` | gauge | **心跳**：最近一次成功运行的 Unix 时间戳 |
| `memory_governance_run_duration_seconds{mode}` | gauge | 最近一次运行耗时 |
| `memory_governance_units_total{mode,outcome}` | counter | 处理的用户数：`scanned` / `succeeded` / `skipped` / `failed`（只在非 0 时建序列） |

语义要点：

- **只有 `result="ok"` 推进心跳**；「没配置 / Mem0 不支持 / 主动关闭」只计数，不伪装成健康。
- 进程启动时把心跳写成启动时间，给新部署一个调度周期内的宽限期；「跑了但一直失败」由
  `result="failed"` 覆盖；「反复重启」由 `up{}` 或容器级 `docker_container_*`
  （node-exporter textfile 采集，见 `deploy/monitoring/README.md`）覆盖。
- 单元计数只在非 0 时建序列，所以告警表达式不能用 `increase(...{outcome="x"}) == 0`
  （序列不存在时返回空向量，规则永不触发），要用 `unless` 表达「没有成功」。

告警规则在 `deploy/prometheus/alerting_rules.yml` 的 `chat_agent_worker_alerts` 组
（日常 staleness、整轮失败、单用户失败、选了人但一个都没治理），抓取配置见
`deploy/prometheus/scrape-config.snippet.yml`。排查顺序：`up` → 心跳 → 失败计数 → 日志。

## 本地验证

```bash
cd backend
# 1) 直接以 Worker 形态启动（复用 backend/.env；Nacos 不可用会回落本地快照）
MEMORY_GOVERNANCE_WORKER__ENABLED=true \
MEMORY_GOVERNANCE_WORKER__RUN_ON_STARTUP=true \
DATABASE__HOST=127.0.0.1 \
CHAT_CONTEXT__MEMORY_CONFIG__BASE_URL=http://127.0.0.1:8899 \
CHAT_CONTEXT__MEMORY_CONFIG__API_KEY=smoke-key \
uv run python -m memory_worker.main
```

`RUN_ON_STARTUP=true` 只触发日跑；周扫可以绕开调度直接调服务：

```python
from sqlmodel import Session
from app.core.db import engine
from app.services.memory_governance.service import MemoryGovernanceService

service = MemoryGovernanceService(session_factory=lambda: Session(engine))
report = await service.run(mode="sweep")   # 日跑：await service.run()
```

也可以绕开调度直接打 Mem0（前提是 `base_url` 指向自建 OSS，且 `api_key` 已配置）：

```bash
curl -X POST "$MEM0_BASE_URL/dream" \
  -H "X-API-Key: <your-api-key>" -H "Content-Type: application/json" \
  -d '{"user_id":"<user_id>","synthesize":true}'
```

测试：`uv run pytest tests/services/memory_governance -q`
（`test_dream_client.py` 覆盖 URL/鉴权/错误语义与三个读接口，`test_service.py` 覆盖
选人（chat/login 两种口径）、水位/门槛闸门、周扫发现、fan-out、重试与失败隔离）。

## 边界与未完成项

- **Platform 不支持外部触发**：`api.mem0.ai` / `/v3` 结尾的 base_url 会被判定为
  Platform 并跳过（Platform 的 Dream 由服务端自行调度，未开放「跑一次 pass」接口）。
  此时水位/门槛读接口也一并跳过（不做拦截），周扫直接返回空报告。
- **admin 列表需要 admin 角色（已核实 dev/prod 两把 key 都满足）**：周扫依赖不带标识符的
  `GET /memories`；服务端在该路径上要求 `role=admin`（或 `ADMIN_API_KEY` / `AUTH_DISABLED`，
  见 `mem0/server/main.py:746-750`），否则 403。已核实（2026-09-21）：`ai-chat-dev` / `ai-chat-prod`
  快照里的 key（`m0sk_2m1e03-` / `m0sk_jMM6Qct`）都归属 mem0 里唯一的 admin 用户且未吊销，
  无标识符列表返回 200（count=6683），伪造 key 返回 401、`AUTH_DISABLED=false`、`ADMIN_API_KEY` 未设置
  —— 即 200 来自 key 自身角色而非「服务端关鉴权」。若日后换成非 admin key，周扫会记日志跳过
  （日跑不受影响）。
- **周扫候选来自 Mem0 存储而不是 chat-agent 用户表**：不带标识符的列表会返回**所有**有记忆的
  user_id（实测含 `hermes-test-verify-r1r2` 这类非 chat-agent 用户）。当前行为是照单全收，
  如需只治理 chat-agent 用户，可在 `collect_sweep_users` 里用 `users.id` 做交集过滤。
- **部署链路已接入**：`docker-compose.yml` 的 `memory-governance`、`deploy.sh`（`DEPLOY_MEMORY_GOVERNANCE`
  环境变量、首次部署服务列表、零停机更新、最终健康检查、镜像清理名单）与 `webhooks/main.py`
  （`MEMORY_GOVERNANCE_DEPLOY_PATHS` + 「backend 要重建就带上它」的推导）已同步。语义：
  worker 跑的是与 backend 同一份代码树（`app/**` + `memory_worker/**`），所以**backend 变更必然重建它**，
  另外 `backend/memory_worker`、`backend/app/services/memory_governance`、`docker-compose.yml`
  单独变更也会触发（`deploy.sh` 直接执行时 `DEPLOY_MEMORY_GOVERNANCE` 默认跟随 `DEPLOY_BACKEND`）。
  健康检查用启动日志行 `Memory governance worker started`（该 worker 没有 HTTP 端口；配置/导入出错时
  进程直接退出、容器停在 Restarting，不会打这行），等待上限 300s —— 容器内 `uv run` 首次会在 `/app`
  重建 `.venv`（实测装 202 个包约 93s），冷启动接近 2 分钟。
- **`backend/Dockerfile` 必须 `COPY memory_worker ./memory_worker`**（2026-09-22 实际踩到）：
  漏掉这一行时镜像里没有该包，容器起来后立刻 `ModuleNotFoundError: No module named 'memory_worker'`
  并进入 restart 循环（`docker ps` 显示 `Restarting`，`RestartCount` 持续增长，日志里只有 uv 建 venv
  与报错）。验证方式：`docker run --rm --entrypoint ls <image> /app` 应能看到 `memory_worker`
  与 `eval_worker` 并列。
- 因为 `enabled` 默认已是 `true`，容器一旦被拉起就会开始按用户打 Mem0——上线时仍要确认三点：
  容器在跑、`memory_config.base_url`/`api_key` 已配、Mem0 侧 `POST /dream` 可访问。
- **cron 字段语义**：日跑/周扫都用 APScheduler 的 `CronTrigger`，其 `day_of_week`
  是 0=周一（与 POSIX cron 的 0=周日不同），所以周扫默认写成 `0 4 * * sun`。
- **观测/告警已接（2026-09-22）**：worker 暴露 Prometheus 指标（心跳 / 运行结局 / 用户数，
  见本文「指标与告警」节），告警规则在 `deploy/prometheus/alerting_rules.yml` 的
  `chat_agent_worker_alerts` 组。线上还差三步（运维侧）：Prometheus 加 scrape job
  （`deploy/prometheus/scrape-config.snippet.yml`）、导入规则文件、配 Alertmanager
  或改用 Grafana 托管告警（实测线上 Prometheus 当时 **0 条规则、无 Alertmanager**）。
- **现网 Mem0 侧现状**：`MEM0_DREAM_ON_ADD=true`（写记忆后同步做轻量 merge/supersede）
  已开启；全量 `POST /dream` 此前只能手动 curl，且 Mem0 自身不带调度器
  （其文档明确要求由 cron 或调用方触发）。
