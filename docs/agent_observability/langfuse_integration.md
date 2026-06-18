# Langfuse 自托管接入说明（Backend）

本文档说明 chat-agent 后端接入 Langfuse（自托管）的配置方式、追踪维度约定与验收方法。

## 1. 配置方式（仅 Nacos）

本项目统一通过 Nacos 下发 Langfuse 配置，不使用 `.env`。

配置位置：`backend/nacos-data/config/ai-chat-dev@@DEFAULT_GROUP@@`

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
- `environment`: 环境标签（如 `dev` / `prod`）

## 2. Trace 维度约定

### 2.1 粒度

- 每轮对话（一次 `/api/chat/stream`）一条 trace
- 使用 `session_id=conversation_id` 聚合同会话多轮

### 2.2 关键标识

- `trace_id`: 由 `assistant_message_id` 派生（确定性）
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
- 工具调用在 `ToolExecutor.execute_single_tool` 中显式创建 `tool` observation

### 3.1 子 span 一览

除根 `chat-turn` span 外，以下环节会显式创建可下钻的子 span（通过 `app.core.observability.observation_span`）：

| Span 名 | 位置 | 说明 |
| --- | --- | --- |
| `history-prepare` | `ChatOrchestrator.run_chat_turn` | 历史窗口准备；输出 `prepared_count`、`has_window_summary`，窗口外摘要 LLM 作为其子 generation |
| `kb-rag-build` | `ChatOrchestrator.run_chat_turn` | KB RAG 组装；输出 `block_count` |
| `memory-search` | `MemoryService.search` | Mem0 检索；输出 `count`、`memory_ids` |
| `title-generation` | `ChatOrchestrator.generate_title_event` | 标题生成；失败标 `ERROR` 但不影响主流程 |
| `memory-write` | `MemoryService.add_memories` | 异步记忆写入；通过 `trace_seed=assistant_message_id` 关联回同一 trace |
| `embedding` | `EmbeddingService` | 用户消息 / 文档向量化；输出 `dimension`、`count` |
| `tool-result-embedding` | `ContextCompactor.extract_relevant_markdown` | 工具结果相关性压缩的向量化 |

所有子 span 的埋点失败只告警、不阻断主链路；业务异常会在标记 `ERROR` 后按原有逻辑继续抛出或返回。

## 4. Token 与成本说明

- 流式 LLM 调用使用 `stream_options={"include_usage": true}`，保证末块返回 usage
- 当前阶段只关注 token（input/output/total）
- 暂不配置金额成本（USD/CNY）映射

## 5. 图片与数据体积控制

多模态消息中图片会以内联 `data:image/...;base64,...` 传给模型。

为避免 trace 膨胀，Langfuse mask 会将这类字符串替换为 `[image omitted]`。

## 6. 失败隔离策略

为保证观测不影响主流程：

- Langfuse 初始化失败只告警，不阻断应用启动
- 不在启动阶段调用 `auth_check`
- 所有埋点调用均做短路与异常保护，异常不冒泡到业务链路
- `enabled=false` 时使用 no-op 行为（`tracing_enabled=false`）

## 7. 故障定位手册（10 分钟）

当用户反馈某轮对话异常时：

1. 根据 `assistant_message_id` 定位 trace（trace_id 确定性派生）
2. 查看该 trace 下的 LLM generation：
   - 延迟、finish reason、token usage、错误类型
3. 查看 tool observation：
   - `tool_name`、参数、返回内容、`status_message`
4. 若为中断场景，检查 trace metadata 中 `status=stopped`
5. 若为失败场景（主会话流式异常），根 span `level=ERROR`、`status_message` 为异常类型，
   metadata 中 `status=failed`，且该轮 **不会**有 done 事件；助手消息落库为 `FAILED`
6. 展开子 span（`history-prepare` / `kb-rag-build` / `memory-search` / `title-generation`
   / `embedding`）定位具体失败环节
7. 结合 `conversation_id` 查看同 session 的相邻轮次趋势

## 8. 验收清单

- [ ] 含工具 + 标题生成的请求产生单条 trace，嵌套关系正确
- [ ] 流式 generation 的 token 非空
- [ ] 图片请求在 trace 中不出现 base64
- [ ] 人工触发工具异常时，observation 标记 `ERROR`
- [ ] 主会话流式中途异常时，根 span 为 `ERROR` 且该轮无 done 事件，助手消息落库为 `FAILED`
- [ ] 记忆检索 / KB RAG 子 span 可展开，含输入输出摘要
- [ ] 标题生成失败时，`title-generation` span 标记 `ERROR`
- [ ] `memory-write` 可通过 `assistant_message_id` 派生的 trace_id 关联到同一 trace
- [ ] Nacos 关闭 `langfuse.enabled` 后，主链路功能正常
