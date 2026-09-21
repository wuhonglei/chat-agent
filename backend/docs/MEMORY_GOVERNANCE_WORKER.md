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
| pass 水位 | `GET /dream?user_id=<id>&limit=1` | 取最近一次 pass 的 `created_at`；失败/为空则不拦截 |
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
3. **水位去重**（`skip_if_governed=true`）：跳过「上次 pass 时间 ≥ 该用户最后一条消息时间」
   的用户——没有新记忆写入就不重跑全量 pass。周扫用户没有可靠的最后活动时间，
   退化用 `min_pass_interval_days`（默认 7 天）兜底。
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

环境变量写法（`__` 嵌套分隔符）：

```bash
MEMORY_GOVERNANCE_WORKER__ENABLED=true
MEMORY_GOVERNANCE_WORKER__SCHEDULE_CRON="0 4 * * *"
MEMORY_GOVERNANCE_WORKER__SWEEP_CRON="0 4 * * sun"
MEMORY_GOVERNANCE_WORKER__MIN_MEMORIES=10
MEMORY_GOVERNANCE_WORKER__CONCURRENCY=2
```

运行报告（`DreamRunReport`）字段：`mode`（daily/sweep）、`scanned_users`、`succeeded`、
`skipped`、`failed`、`failures`；每个用户一条 `UserDreamOutcome`，含
`status`（ok/skipped/failed）、`reason`（跳过原因，如 `governed_after_last_message`、
`below_min_memories:3<10`）、`attempts`、`pass_id`、`stats`。

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
- **部署脚本未接入（默认开启后需注意）**：`deploy.sh` 的服务列表与
  `webhooks/main.py` 的变更路径判定目前只覆盖 backend / frontend / evaluator / sites；
  新服务不在其中就没有首启与零停机更新（首启需手动
  `docker compose up -d memory-governance`）。因为 `enabled` 默认已是 `true`，一旦容器
  被拉起就会开始按用户打 Mem0；反过来，若没人启动容器，配置里开着也不会执行——
  上线时要同时确认这三点：容器在跑、`memory_config.base_url`/`api_key` 已配、
  Mem0 侧 `POST /dream` 可访问。
- **cron 字段语义**：日跑/周扫都用 APScheduler 的 `CronTrigger`，其 `day_of_week`
  是 0=周一（与 POSIX cron 的 0=周日不同），所以周扫默认写成 `0 4 * * sun`。
- **观测/告警未接**：目前只有结构化日志；后续可加 Prometheus 指标（success/failure/
  duration）与失败告警，必要时把治理 pass 结果落库做长期趋势。
- **现网 Mem0 侧现状**：`MEM0_DREAM_ON_ADD=true`（写记忆后同步做轻量 merge/supersede）
  已开启；全量 `POST /dream` 此前只能手动 curl，且 Mem0 自身不带调度器
  （其文档明确要求由 cron 或调用方触发）。
