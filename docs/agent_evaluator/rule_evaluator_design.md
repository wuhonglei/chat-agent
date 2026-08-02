# Rule Evaluator 实时规则评估器 — 落地方案

> 目标：每轮问答结束后同步执行 3 个 P0 规则指标，写入 Langfuse score
> 延迟要求：< 10ms，不阻塞用户请求
> 前置条件：Langfuse 升级至 v4+（自托管版支持 Monitors & Alerts）

---

## 一、指标清单

| 指标名            | 分值类型 | 判定逻辑                   | 阈值        | 说明                         |
| ----------------- | -------- | -------------------------- | ----------- | ---------------------------- |
| valid_answer      | 布尔     | `len(content.strip()) > 0` | true = 合格 | 回答完全为空时判 false       |
| tool_whitelist_ok | 布尔     | 调用工具组合名 ⊆ 场景白名单 | true = 合格 | 两种 agent_mode 均按白名单判定 |
| tool_call_count   | 数值     | `ToolUseBlock` 计数        | <= 5        | 单轮工具调用过多可能是死循环 |

**不在实时链路中处理的 P0 指标**（Langfuse 已自动记录，Monitors 告警或离线回查）：

| 指标名       | 原因                                                                                              |
| ------------ | ------------------------------------------------------------------------------------------------- |
| latency_e2e  | Langfuse trace 的 `start_time` / `end_time` 已记录，Monitors 可设 p95 < 8s 告警                   |
| input_tokens | `langfuse.openai.AsyncOpenAI` 自动记录 generation span 的 usage，Monitors 可设 < 8000 告警       |

---

## 二、工具白名单设计

### 2.1 命名规则

LLM 可见的工具组合名格式：`{server_name}_{bare_name}`（见 `app/mcp/tool_naming.py`）

```
示例：
  tavily_web_search       → server=tavily, tool=web_search
  file_read_file          → server=file,   tool=read_file
  code_execute_code       → server=code,   tool=execute_code
  skill_manager_load_skill → server=skill_manager, tool=load_skill
```

### 2.2 白名单来源

白名单不硬编码，从 `settings.mcp` 的 server 列表动态派生：

```
agent_mode=0 → settings.mcp.normal_mode_servers = ["time", "weather", "tavily", "code", "context7", "zread"]
agent_mode>0 → settings.mcp.agent_mode_servers  = ["file", "skill_manager", "shell", "tavily", "context7", "zread"]
```

白名单 = 每个 server 下已注册到 `mcp_manager.tools_map` 的工具组合名集合。

> 普通模式（`agent_mode=0`）也会暴露 `normal_mode_servers` 工具给 LLM，因此**不能**按「零工具调用」判定，统一用 ⊆ 白名单。

### 2.3 白名单构建方式

**方案 A（已采用）：运行时从 `tools_map` 派生**

MCP gateway 启动时已注册所有工具路由（`app/mcp/gateway.py` 的 `tools_map`）。按当前 `agent_mode` 对应的 server 列表过滤：

```python
def build_tool_whitelist(
    agent_mode: int,
    tools_map: dict[str, ToolRoute],
) -> set[str]:
    """从 MCP tools_map 构建当前 agent_mode 的工具白名单。"""
    if agent_mode > 0:
        server_names = set(settings.mcp.agent_mode_servers)
    else:
        server_names = set(settings.mcp.normal_mode_servers)
    return {
        name
        for name, route in tools_map.items()
        if route.server_name in server_names
    }
```

每轮从 `tools_map` 构建（O(工具数)，远低于 10ms），MCP reload 后自然生效，无需额外缓存。

**方案 B：静态枚举（备选，需维护）**

在 `app/mcp/constants.py` 中已有部分 LLM name 常量，补全后直接引用。

### 2.4 判定逻辑

```python
has_unnamed = any(
    isinstance(block, ToolUseBlock) and not block.name for block in content_blocks
)
called_tools = {
    block.name
    for block in content_blocks
    if isinstance(block, ToolUseBlock) and block.name
}
whitelist = build_tool_whitelist(agent_mode, tools_map)
whitelist_ok = (not has_unnamed) and called_tools.issubset(whitelist)
```

**特殊情况**：

- 工具名为空（`name=None`）：视为未知工具，判 `tool_whitelist_ok=false`。

---

## 三、数据来源与提取

### 3.1 valid_answer

```python
content = assistant_response.content  # str，LLM 最终回复文本
is_valid = len(content.strip()) > 0
```

数据来源：`chat_orchestrator.py` 成功路径中 `collect_assistant_response().content`

### 3.2 tool_whitelist_ok

```python
content_blocks = assistant_response.content_blocks  # list[ContentBlock]
```

数据来源：同上 `content_blocks`；白名单来自 `chat_session_agent.mcp_manager.tools_map`。

### 3.3 tool_call_count

```python
tool_count = count_tool_use_blocks(content_blocks)
```

数据来源：同上，复用 `count_tool_use_blocks()`（`app/schemas/chat.py`）。

---

## 四、Langfuse Score 写入

复用已有基础设施 `app/core/observability.py:score_observation()`：

```python
score_observation(
    root_span,                     # chat_orchestrator 的 root_span
    name="valid_answer",
    value=True,                    # bool，true=非空合格
    data_type="BOOLEAN",
)

score_observation(
    root_span,
    name="tool_whitelist_ok",
    value=False,
    data_type="BOOLEAN",
    comment="called={'shell_exec'}",
)

score_observation(
    root_span,
    name="tool_call_count",
    value=3,
    data_type="NUMERIC",
)
```

score 挂在 root_span（`chat-turn` span）上，Langfuse UI 中展开该 trace 即可看到。

---

## 五、Langfuse Monitors & Alerts 配置

升级 Langfuse v4 后，在 Langfuse UI 中配置 Monitors 实现自动告警。

### 5.1 Boolean Score Monitors

| Monitor 名称        | 数据源           | 指标                     | 警告阈值 | 告警阈值 |
| ------------------- | ---------------- | ------------------------ | -------- | -------- |
| valid_answer_rate   | Scores (boolean) | avg(valid_answer)        | < 0.98   | < 0.95   |
| tool_whitelist_rate | Scores (boolean) | avg(tool_whitelist_ok)   | < 0.99   | < 0.97   |

Boolean score 的 avg 值 = true 的占比，即通过率。

### 5.2 Numeric Score Monitors

| Monitor 名称        | 数据源           | 指标                   | 警告阈值 | 告警阈值 |
| ------------------- | ---------------- | ---------------------- | -------- | -------- |
| tool_call_count_p95 | Scores (numeric) | p95(tool_call_count)   | > 4      | > 5      |
| latency_e2e_p95     | Observations     | p95(latency)           | > 6s     | > 8s     |
| input_tokens_avg    | Observations     | avg(input_tokens)      | > 6000   | > 8000   |

### 5.3 告警通知渠道

Langfuse v4 Monitors 支持以下通知方式：

| 渠道           | 配置方式                                       | 适用场景       |
| -------------- | ---------------------------------------------- | -------------- |
| Slack          | Langfuse Settings → Integrations → Slack       | 团队即时通知   |
| Webhook        | Langfuse Settings → Integrations → Webhook URL | 自定义系统对接 |
| GitHub Actions | Langfuse Settings → Integrations → GitHub      | CI/CD 流程联动 |

建议：Slack 作为主告警渠道，Webhook 备用（可对接飞书/企微等）。

### 5.4 Score Analytics

Langfuse v4 的 Score Analytics 面板（Dashboards 页面）：

- Trend Over Time：跟踪各指标随时间的变化趋势
- Distribution：查看 score 值的分布情况
- Compare：对比两个 score 的关联性（如 valid_answer vs tool_whitelist_ok）
- 统计摘要：count、mean、standard deviation

无需额外配置，score 写入后自动出现在 Analytics 面板中。

---

## 六、代码结构

### 6.1 新增文件

```
backend/app/evaluators/
├── __init__.py
└── rule_evaluator.py      # 评估逻辑（仅写 Langfuse score）
```

### 6.2 rule_evaluator.py 模块设计

见实现：`backend/app/evaluators/rule_evaluator.py`。

核心 API：

- `build_tool_whitelist(agent_mode, tools_map) -> set[str]`
- `evaluate_and_score(*, span, assistant_response, agent_mode, tool_whitelist) -> None`

指标写入：

- `valid_answer`：BOOLEAN，`true` = 非空合格
- `tool_whitelist_ok`：BOOLEAN；失败时 `comment` 带 `called=...`
- `tool_call_count`：NUMERIC

---

## 七、插入点：chat_orchestrator.py

### 7.1 修改位置

`app/services/chat/chat_orchestrator.py` 的 `run_chat_turn` 成功结束路径：

```python
assistant_response = self.collect_assistant_response()
assistant_updated_at = self.post_process_service.persist_final_assistant_message(...)
await invalidate_conversation_state(...)

# ---- 规则评估 ----
mcp_manager = getattr(self.chat_session_agent, "mcp_manager", None)
tools_map = mcp_manager.tools_map if mcp_manager is not None else {}
evaluate_and_score(
    span=root_span,
    assistant_response=assistant_response,
    agent_mode=chat_request.agent_mode,
    tool_whitelist=build_tool_whitelist(chat_request.agent_mode, tools_map),
)

if trace_enabled and langfuse_client is not None and root_span is not None:
    root_span.update(output=assistant_response.content)
```

仅成功完成路径调用；失败/取消路径不评估。

### 7.2 白名单策略

本次采用**每轮从 `tools_map` 构建**，不在 Orchestrator 上缓存。若后续需要更进一步优化，可在 init 缓存并在 MCP reload 回调中重建（见第十节）。

---

## 八、失败与边界处理

| 场景                      | 处理方式                                               |
| ------------------------- | ------------------------------------------------------ |
| 评估函数抛异常             | `logger.warning` 记录，不影响主链路（SSE 流正常返回） |
| Langfuse 未启用           | `score_observation` 内部已处理（span=None 时 no-op）   |
| content_blocks 为空列表   | tool_whitelist_ok=True, tool_call_count=0              |
| ToolUseBlock.name 为 None | 视为未知工具，判 tool_whitelist_ok=false               |

---

## 九、升级前置条件

本方案依赖 Langfuse v4 的 Monitors & Alerts 功能。

| 检查项            | 当前状态     | 目标状态        |
| ----------------- | ------------ | --------------- |
| Langfuse 版本     | v3.214.0     | v4.2.0+         |
| Python SDK 版本   | 需确认       | 兼容 v4 的最新版 |
| Monitors & Alerts | 不可用（v3） | v4 自托管版支持 |
| Score Analytics   | 不可用（v3） | v4 支持         |

升级完成后：

1. 在 Langfuse UI 中配置 Monitors（见第五节）
2. 部署 rule_evaluator 代码
3. 观察 1-2 周，确认阈值合理后调整 Monitors 配置

---

## 十、后续扩展（不在本次范围）

1. **离线评估脚本**：从 Langfuse API 拉取 latency_e2e、input_tokens，计算 p95 并写 score
2. **P1 指标接入**：answer_completeness / answer_correctness（LLM-as-Judge，异步 worker）
3. **bad case 回流**：valid_answer=false 或 tool_whitelist_ok=false 的 trace 自动进复核队列
4. **白名单缓存 + 热更新**：Orchestrator 缓存白名单，MCP 配置热更新时自动重建
