# Langfuse 自托管接入与运维手册（Backend）

本文档说明 chat-agent 后端接入 Langfuse（自托管）的配置方式、追踪维度约定、
数据同步脚本和排障步骤。内容以当前源码为准，重点覆盖：

- 运行时埋点：`backend/app/core/observability.py`、
  `backend/app/services/chat/chat_orchestrator.py`
- LLM / 工具 / 记忆子 observation：`LLMService`、`ToolExecutor`、`MemoryService`
- 离线运维脚本：`backend/scripts/sync_feedback_to_langfuse.py`、
  `backend/scripts/sync_status_to_langfuse.py`、根目录 `scripts/*langfuse*.py`

## 1. 配置方式

现网约定通过 Nacos 下发 Langfuse 配置。开发环境默认读取：
`backend/nacos-data/config/ai-chat-dev@@DEFAULT_GROUP@@`；
生产环境对应 `ai-chat-prod@@DEFAULT_GROUP@@`。

```yaml
langfuse:
  enabled: false
  host: ""
  public_key: ""
  secret_key: ""
  sample_rate: 1.0
  debug: false
  environment: "dev"
```

字段说明：

- `enabled`: 是否开启追踪
- `host`: 自托管 Langfuse 地址
- `public_key` / `secret_key`: API Key
- `sample_rate`: 采样率（0~1）
- `debug`: SDK debug 日志
- `environment`: 环境标签（如 `dev` / `prod`）。评估 Worker 覆盖为 `eval_worker`

### 1.1 启动与关闭

- FastAPI lifespan 在启动时调用 `init_langfuse()`；初始化失败只记录 warning，
  不阻断应用启动。
- 关闭时调用 `shutdown_langfuse()`，会尝试 `flush()` 缓冲队列，避免进程退出丢事件。
- `init_langfuse()` 会设置 `OTEL_SERVICE_NAME=chat-agent-backend`（仅在环境变量未显式设置时）。
- 独立 `eval_worker` 进程在导入时 `setdefault`：`LANGFUSE__ENVIRONMENT=eval_worker`、
  `OTEL_SERVICE_NAME=chat-agent-eval-worker`（Compose `evaluator` 服务同样注入）。
  裁判调用会创建名为 `eval-judge`、类型 `evaluator` 的 observation。
- `enabled=false` 时会以 `tracing_enabled=false` 尝试初始化；无论 client 是否创建成功，
  业务侧 `observation_span()` 都会退化为 no-op。

## 2. Trace 维度约定

### 2.1 粒度

- 每轮对话（一次 `POST /api/chat/stream`）一条 trace
- 使用 `session_id=conversation_id` 聚合同会话多轮

### 2.2 关键标识

- `trace_id`: 由 `assistant_message_id` 确定性派生：
  `Langfuse.create_trace_id(seed=assistant_message_id)`；若 SDK 不可用，回退为
  `sha256(assistant_message_id)[:32]`
- `session_id`: `conversation_id`
- `user_id`: JWT 用户 ID

### 2.3 元数据

`chat-turn` trace 会写入以下 metadata：

- `conversation_id`
- `user_message_id`
- `assistant_message_id`
- `model_id`
- `agent_mode`
- `client_turn_id`

## 3. 覆盖范围

单轮 trace 覆盖：

1. 历史准备（含窗口外摘要）
2. 记忆检索
3. KB RAG 组装
4. 主 Agent 流式 LLM 调用
5. MCP 工具调用
6. 最终落库与 done 事件

其中：

- LLM generation 由 `langfuse.openai.AsyncOpenAI` 自动采集
- 工具调用在 `ToolExecutor.execute_single_tool` 中显式创建 `tool` observation，
  并在 observation 上写入 BOOLEAN score `tool_success`：
  - 默认：非空结果为成功；空结果 `false` + `error_type=empty_result`
  - `shell`：以 `structured_content.exit_code == 0` 为成功；`blocked` /
    `timed_out` / 非 0 退出码为失败
  - `code`：以 `run.code == 0` 为成功；编译非 0 / 运行非 0 / `signal` 为失败
  - 异常路径：`false` + 异常类名，并标记 observation `ERROR`
  成功率 KPI 以 score 为准。
- `LLMService` 在连接失败、限流或 API 状态异常时会把当前 LLM observation 标记为 `ERROR`
- 失败隔离：所有观测失败只告警，不改变业务响应

### 3.1 子 span 一览

除根 `chat-turn` span 外，以下环节会显式创建可下钻的子 span（通过 `app.core.observability.observation_span`）：

| Span 名 | 位置 | 说明 |
| --- | --- | --- |
| `history-prepare` | `ChatOrchestrator.run_chat_turn` | 历史窗口准备；输出 `prepared_count`、`has_window_summary`，窗口外摘要 LLM 作为其子 generation |
| `kb-rag-build` | `ChatOrchestrator.run_chat_turn` | KB RAG 组装；输出 `block_count` |
| `memory-search` | `MemoryService.search` | Mem0 检索；输出 `count` 与命中的 memory 列表 |
| `title-generation` | `ChatOrchestrator.generate_title_event` | 标题生成；失败标 `ERROR` 但不影响主流程 |
| `embedding` | `EmbeddingService` | 用户消息 / 文档向量化；输出 `dimension`、`count` |
| `tool-result-embedding` | `ContextCompactor.extract_relevant_markdown` | 工具结果相关性压缩的向量化 |

注意：`memory-write` 通过 `asyncio.create_task()` 异步执行，当前不单独创建 Langfuse
trace，避免与 `chat-turn` 共用 trace ID 时产生第二条 root observation。

所有子 span 的埋点失败只告警、不阻断主链路；业务异常会在标记 `ERROR` 后按原有逻辑继续抛出或返回。

## 4. Token 与成本说明

- 流式 LLM 调用使用 `stream_options={"include_usage": true}`，保证末块返回 usage
- 当前阶段只关注 token（input/output/total）
- 暂不配置金额成本（USD/CNY）映射

## 5. 图片与数据体积控制

多模态消息中图片会以内联 `data:image/...;base64,...` 传给模型。

为避免 trace 膨胀，Langfuse mask 会将这类字符串替换为 `[image omitted]`。

## 6. Score 同步脚本

后端脚本用于把数据库中的助手消息状态和用户反馈补写到 Langfuse Score。运行前需确认：

1. Nacos 配置存在并包含 `langfuse.host/public_key/secret_key` 与 `database.*`
2. 目标 Langfuse 中已经有由同一 `assistant_message_id` 派生的 trace
3. 先执行 `--dry-run` 观察命中量、跳过量和错误量

### 6.1 反馈同步

脚本：`backend/scripts/sync_feedback_to_langfuse.py`

```bash
cd backend
python scripts/sync_feedback_to_langfuse.py --dry-run
python scripts/sync_feedback_to_langfuse.py --prod --dry-run
python scripts/sync_feedback_to_langfuse.py --prod

# 如需指定配置文件：
NACOS_CONFIG=/path/to/ai-chat-prod@@DEFAULT_GROUP@@ \
  python scripts/sync_feedback_to_langfuse.py --dry-run
```

行为约束：

- 读取 `messages.feedback`，仅同步 `role='assistant'` 且 `feedback.value != 'default'` 的消息
- `like -> 1.0`，`dislike -> 0.0`，`default` 跳过
- score 名称为 `user_feedback`
- comment 包含 `message_id`、`conversation_id`、`feedback_updated_at`、`status`
- 写入前会查询 Langfuse traces（当前 API limit 为 50），不存在的 trace 会跳过

### 6.2 状态同步

脚本：`backend/scripts/sync_status_to_langfuse.py`

```bash
cd backend
python scripts/sync_status_to_langfuse.py --dry-run
python scripts/sync_status_to_langfuse.py --prod --dry-run
python scripts/sync_status_to_langfuse.py --prod
```

行为约束：

- 读取 `role='assistant'` 且 `status in ('done', 'stopped', 'failed')` 的消息
- `done -> 1.0`，`stopped -> 0.5`，`failed -> 0.0`
- score 名称为 `message_status`
- comment 包含 `message_id`、`status`、`updated_at`
- 写入前会查询 Langfuse traces（当前 API limit 为 100），不存在的 trace 会跳过

### 6.3 历史导入与回放脚本

根目录 `scripts/` 下还有历史数据导入、分析和回放工具：

- `scripts/import_to_langfuse.py`：把 JSON 问答数据导入 Langfuse，trace ID 为
  `trace_{conversation_id}`，并创建 `response_latency` span、`tool_execution` generation、
  `response_time_quality` score
- `scripts/sync_scores_to_langfuse.py`：从数据库读取助手消息状态并写入 `message_status`
  score，trace ID 为 `trace_{sha256(message_id)[:32]}`
- `scripts/replay_qa_pairs.py`：通过 HTTP API 重放历史问题，要求通过
  `--username/--password` 或 `REPLAY_USERNAME/REPLAY_PASSWORD` 提供登录凭证

这些根目录脚本与当前后端运行时 trace ID 规则不完全一致；用于历史迁移或实验分析时，
需要先在 `--dry-run` / `--help` 下确认目标环境、输入数据和 trace 关联方式。尤其是
`replay_qa_pairs.py` 当前请求体和路径仍按旧同步聊天接口编写，不应直接作为现网
`POST /api/chat/stream` 的压测脚本。

## 7. 失败隔离策略

为保证观测不影响主流程：

- Langfuse 初始化失败只告警，不阻断应用启动
- 不在启动阶段调用 `auth_check`
- 所有埋点调用均做短路与异常保护，异常不冒泡到业务链路
- `enabled=false` 时使用 no-op 行为（`tracing_enabled=false`）

## 8. 故障定位手册（10 分钟）

当用户反馈某轮对话异常时：

1. 根据 `assistant_message_id` 定位 trace（trace_id 确定性派生）
2. 查看该 trace 下的 LLM generation：
   - 延迟、finish reason、token usage、错误类型
3. 查看 tool observation：
   - `tool_name`、参数、返回内容、`status_message`
   - Scores 中的 `tool_success`（BOOLEAN）及失败时的 `error_type`
4. 若为中断场景，检查 trace metadata 中 `status=stopped`
5. 若为失败场景（主会话流式异常），根 span `level=ERROR`、`status_message` 为异常类型，
   metadata 中 `status=failed`，且该轮 **不会**有 done 事件；助手消息落库为 `FAILED`
6. 展开子 span（`history-prepare` / `kb-rag-build` / `memory-search` / `title-generation`
   / `embedding`）定位具体失败环节
7. 结合 `conversation_id` 查看同 session 的相邻轮次趋势
8. 如果用户反馈/状态 score 缺失：
   - 先确认助手消息 ID 对应的 trace 是否存在
   - 再用 `--dry-run` 执行同步脚本，查看 `No trace in Langfuse` / `Errors` 统计
   - 检查 `messages.feedback.value` 是否为 `default`（该值会被跳过）

## 9. 验收清单

- [ ] 含工具 + 标题生成的请求产生单条 trace，嵌套关系正确
- [ ] 流式 generation 的 token 非空
- [ ] 图片请求在 trace 中不出现 base64
- [ ] 人工触发工具异常时，observation 标记 `ERROR`，且 `tool_success=false`
- [ ] 正常工具调用产生 `tool_success=true`；空结果产生 `tool_success=false`
- [ ] 主会话流式中途异常时，根 span 为 `ERROR` 且该轮无 done 事件，助手消息落库为 `FAILED`
- [ ] 记忆检索 / KB RAG 子 span 可展开，含输入输出摘要
- [ ] 标题生成失败时，`title-generation` span 标记 `ERROR`
- [ ] `sync_feedback_to_langfuse.py --dry-run` 能列出可同步、跳过和缺 trace 的数量
- [ ] `sync_status_to_langfuse.py --dry-run` 能列出 done/stopped/failed 分布
- [ ] Nacos 关闭 `langfuse.enabled` 后，主链路功能正常
