# 评估运维手册（现网）

覆盖分层采样评估 Worker、Bad Case 复核队列与 CI 评估门禁。设计背景见 `batch_eval_worker_design.md`（文首含现网差异摘要）；规则评估器设计见 `docs/agent_evaluator/rule_evaluator_design.md`。

## 1. 组件与入口

| 组件 | 路径 | 作用 |
|------|------|------|
| Eval Worker | `backend/eval_worker/main.py` | APScheduler 定时跑批量裁判评估 |
| 批量编排 | `app/services/eval/batch_eval_service.py` | 拉 Trace → 去重 → 采样 → judge → 写分/入队 |
| 分层采样 | `app/evaluators/sampler.py` | 特殊场景 100% + 风险分层抽样 |
| 实时规则评估 | `app/evaluators/rule_evaluator.py` | 聊天结束后打规则分；失败可入队 |
| Bad Case API | `app/api/eval.py` → `/api/eval/*` | 复核队列 CRUD |
| 手动批评 | `scripts/run_batch_eval.py` | 调试 / 补跑 |
| CI 门禁 | `scripts/run_eval_gate.py` | frozen / replay 回归 |
| Replay | `scripts/eval_replay.py` | 门禁 replay 模式调用真实 API |

## 2. Eval Worker 配置

配置模型：`EvalWorkerConfig`（`settings.eval_worker`）。环境变量前缀 `EVAL_WORKER__*`。

| 字段 | 默认 | 说明 |
|------|------|------|
| `enabled` | `True` | `false` 时进程仍启动，但定时 job 跳过 |
| `schedule_cron` | `0 17 * * *` | 5 段 cron；时区 **Asia/Shanghai** |
| `lookback_hours` | `24` | 拉取最近 N 小时 Trace |
| `sample_rate_high` | `0.40` | 高风险采样比例 |
| `sample_rate_medium` | `0.15` | 中风险 |
| `sample_rate_low` | `0.05` | 低风险 |
| `judge_low_score_threshold` | `3` | 低于此分入队 `source=low_score` |
| `quick_follow_up_threshold_s` | `30` | 快速追问特殊采样阈值（秒） |
| `high_latency_threshold_s` | `30.0` | 高延迟特殊采样阈值（秒） |
| `judge_concurrency` | `5` | 裁判并发 |
| `judge_timeout_s` | `60.0` | 单条裁判超时 |
| `judge_model_scenario` | `judge` | 对应 `models.scenarios.judge` |

### 分层与特殊场景（方案 A）

- **特殊场景（100% 采样）**：用户点踩（`thumb_down`）、快速追问、延迟 > `high_latency_threshold_s`。
- **高风险工具**（LLM 名）：`code_execute_code`、`file_write_file`、`file_edit_file`、`shell_exec`。
- **中风险**：`tavily_web_search`、`tavily_web_pages_extract`、`tavily_web_site_crawl`、`context7_resolve-library-id`、`context7_query-docs`；未名单但有工具调用也按中风险。
- **低风险**：无工具调用的纯模型回答。

设计稿中的 embedding 聚类 / bad_case 相似度 100% 采样 **尚未实现**。

## 3. 启停与手动触发

```bash
# Compose（推荐联调）
docker compose up evaluator
# 容器命令: uv run python -m eval_worker.main
# 已注入 EVAL_WORKER__ENABLED=true、DATABASE__HOST=postgres；资源上限 512M / 0.5 CPU

# 本机 worker
cd backend && uv run python -m eval_worker.main

# 手动批评（可覆盖 lookback；dry-run 只采样不调裁判）
cd backend && uv run python scripts/run_batch_eval.py [--hours 24] [--dry-run]
```

依赖：PostgreSQL、Langfuse、`models.scenarios.judge` 可用。运行日志写入 `eval_run_logs` 表；**无** HTTP 查询 API，排障看 worker 日志或直查 DB。

## 4. Bad Case 复核队列

前缀：`/api/eval`。**均需 JWT，且 `users.role = admin`**（非 admin 返回 403）。

前端管理页：`/admin/bad-cases`（仅 admin 可见入口与可访问）。

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/bad-cases` | 分页列表；可选 `status` / `source` / `attribution`；`page` 默认 1，`page_size` 默认 20 |
| GET | `/bad-cases/stats` | 队列统计 |
| GET | `/bad-cases/{item_id}` | 详情 |
| PUT | `/bad-cases/{item_id}` | 更新 `status` / `attribution` / `reviewer_notes` / `resolution` |
| POST | `/bad-cases/{item_id}/add-to-dataset` | 推送到固定 Langfuse Dataset，并置 `resolution=added_to_dataset`、`status=resolved` |

响应中若有 `trace_id`，会附带 `langfuse_trace_url` 供前端跳转 Trace UI。

### Dataset / Trace 相关配置（`LANGFUSE__*`）

| 字段 | 默认 | 说明 |
|------|------|------|
| `BAD_CASE_DATASET_NAME` | `chat-agent-bad-cases` | 复核推送的固定 Dataset 名 |
| `PROJECT_ID` | `""` | 可选；有值时 Trace URL 为 `{host}/project/{id}/traces/{trace_id}`，否则 `{host}/trace/{trace_id}` |

推送使用 `create_dataset_item(id=bad_case.id)` upsert，重复点击不会产生重复条目。

### 入队来源 `source`

| 值 | 触发 |
|----|------|
| `rule_fail` | 实时规则评估失败（`chat_orchestrator`） |
| `thumb_down` | `PUT /api/message/feedback` 且 `value=dislike`（异步） |
| `low_score` | 批量裁判分 < `judge_low_score_threshold` |

### 状态 `status`

`pending` → `reviewing` → `resolved` / `dismissed`。

用户将反馈改回 `value=default`（取消点踩）时，会 dismiss 该消息下仍为 `pending` 的 `thumb_down` 条目。

## 5. CI 评估门禁

```bash
# frozen（默认，不依赖本地服务）
cd backend && uv run python scripts/run_eval_gate.py

# replay（需服务可达 + JWT）
uv run python scripts/run_eval_gate.py --replay --token <jwt>
# 或 EVAL_GATE_TOKEN=... ；默认 base URL http://localhost:8000

# 自定义阈值 / 只评估不门禁 / baseline
uv run python scripts/run_eval_gate.py --min-correctness 4.6 --min-completeness 4.4
uv run python scripts/run_eval_gate.py --no-gate
uv run python scripts/run_eval_gate.py --save-baseline
```

| 模式 | 行为 |
|------|------|
| `frozen` | 对冻结历史回答打裁判分（检测标注/裁判漂移） |
| `replay` | 对每条 query 调真实 API 重生回答再裁判（检测 prompt/模型/架构变化） |

默认阈值：`correctness ≥ 4.5`，`completeness ≥ 4.3`。退出码：`0` 通过 / `1` 门禁失败 / `2` 运行错误。

Replay 拉取消息时使用 `GET /api/conversation/{id}/messages?full_content=true`，避免 tool_result 被结构化展示字段省略。

## 6. 常见坑

- cron 默认是 **17:00 Asia/Shanghai**，不是设计稿里的凌晨 3 点。
- `enabled=false` 不会退出进程，只跳过 job；Compose 里显式写了 `EVAL_WORKER__ENABLED=true`。
- 风险分层认的是 **MCP LLM 工具名**（`{server}_{bare}`），不是旧文档里的 `execute_code` / `shell`。
- 点踩入队与取消 dismiss 均为 fire-and-forget；失败只打 warning，不阻断反馈 API。
- 门禁 replay 需要本机后端 + 有效 JWT；frozen 模式更适合 CI。
