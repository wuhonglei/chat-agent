# Rule Evaluator 实时规则评估器 — 落地方案

> 目标：每轮问答结束后同步执行 3 个 P0 规则指标，写入 Langfuse score
> 延迟要求：< 10ms，不阻塞用户请求
> 前置条件：Langfuse 升级至 v4+（自托管版支持 Monitors & Alerts）

---

## 一、指标清单

| 指标名             | 分值类型 | 判定逻辑                                    | 阈值       | 说明                              |
| ------------------ | -------- | ------------------------------------------- | ---------- | --------------------------------- |
| empty_answer       | 布尔     | `len(content.strip()) > 0`                  | true = 合格 | 回答完全为空时判 false            |
| tool_whitelist_ok  | 布尔     | 调用工具组合名 ⊆ 场景白名单                  | true = 合格 | agent_mode=0 不应出现任何工具调用 |
| tool_call_count    | 数值     | `ToolUseBlock` 计数                         | <= 5       | 单轮工具调用过多可能是死循环      |

**不在实时链路中处理的 P0 指标**（Langfuse 已自动记录，Monitors 告警或离线回查）：

| 指标名         | 原因                                                          |
| -------------- | ------------------------------------------------------------- |
| latency_e2e    | Langfuse trace 的 `start_time` / `end_time` 已记录，Monitors 可设 p95 < 8s 告警 |
| input_tokens   | `langfuse.openai.AsyncOpenAI` 自动记录 generation span 的 usage，Monitors 可设 < 8000 告警 |

---

## 二、工具白名单设计

### 2.1 命名规则

LLM 可见的工具组合名格式：`{server_name}_{bare_name}`（见 `app/mcp/tool_naming.py:17`）

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

白名单 = 每个 server 下注册的所有工具的组合名集合。

### 2.3 白名单构建方式

两种方案，推荐方案 A：

**方案 A：运行时从 MCP registry 查询（推荐）**

MCP gateway 启动时已注册所有工具路由（`app/mcp/gateway.py`）。遍历当前 agent_mode 对应的 server 列表，收集已注册的工具组合名。

```python
def build_tool_whitelist(
    agent_mode: int,
    mcp_gateway: MCPGateway,
) -> set[str]:
    """从 MCP registry 构建当前 agent_mode 的工具白名单。"""
    if agent_mode <= 0:
        server_names = settings.mcp.normal_mode_servers
    else:
        server_names = settings.mcp.agent_mode_servers

    whitelist: set[str] = set()
    for server_name in server_names:
        for tool in mcp_gateway.get_tools_by_server(server_name):
            whitelist.add(llm_tool_name(server_name, tool.name))
    return whitelist
```

**方案 B：静态枚举（简单但需维护）**

在 `app/mcp/constants.py` 中已有部分 LLM name 常量，补全后直接引用。

```python
# 已有常量（app/mcp/constants.py）
WEB_SEARCH_LLM    = "tavily_web_search"
READ_FILE_LLM     = "file_read_file"
WRITE_FILE_LLM    = "file_write_file"
EXECUTE_CODE_LLM  = "code_execute_code"
SHELL_LLM         = "shell_exec"
# ... 需补全 time、weather、context7、zread、skill_manager 的常量
```

### 2.4 判定逻辑

```python
called_tools = {block.name for block in content_blocks if isinstance(block, ToolUseBlock)}
whitelist = build_tool_whitelist(agent_mode, mcp_gateway)
whitelist_ok = called_tools.issubset(whitelist)
```

**特殊情况**：
- `agent_mode=0`（普通模式）：理论上不应有任何工具调用。如果出现 ToolUseBlock，直接判 false。
- 工具名为空（`name=None`）：ToolUseBlock 的 `name` 可能为 None（未知/过时工具名），这种情况也判 false。

---

## 三、数据来源与提取

### 3.1 empty_answer

```python
content = assistant_response.content  # str，LLM 最终回复文本
is_non_empty = len(content.strip()) > 0
```

数据来源：`chat_orchestrator.py:522` 的 `collect_assistant_response().content`

### 3.2 tool_whitelist_ok

```python
content_blocks = assistant_response.content_blocks  # list[ContentBlock]
called_tools = {block.name for block in content_blocks if isinstance(block, ToolUseBlock)}
```

数据来源：`chat_orchestrator.py:522` 的 `collect_assistant_response().content_blocks`

需要注入：`mcp_gateway` 实例（用于构建白名单）或预计算的白名单 set

### 3.3 tool_call_count

```python
tool_count = sum(1 for block in content_blocks if isinstance(block, ToolUseBlock))
```

数据来源：同上，复用 `count_tool_use_blocks()` 函数（`chat.py:571` 已存在）

---

## 四、Langfuse Score 写入

复用已有基础设施 `app/core/observability.py:score_observation()`：

```python
score_observation(
    root_span,                     # chat_orchestrator 的 root_span
    name="empty_answer",
    value=True,                    # bool
    data_type="BOOLEAN",
)

score_observation(
    root_span,
    name="tool_whitelist_ok",
    value=False,
    data_type="BOOLEAN",
    comment="called={'shell_exec'}, allowed={'tavily_web_search', ...}",
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

| Monitor 名称         | 数据源        | 指标              | 警告阈值       | 告警阈值       |
| -------------------- | ------------- | ----------------- | -------------- | -------------- |
| empty_answer_rate    | Scores (boolean) | avg(empty_answer) | < 0.98        | < 0.95         |
| tool_whitelist_rate  | Scores (boolean) | avg(tool_whitelist_ok) | < 0.99   | < 0.97         |

Boolean score 的 avg 值 = true 的占比，即通过率。

### 5.2 Numeric Score Monitors

| Monitor 名称         | 数据源        | 指标              | 警告阈值       | 告警阈值       |
| -------------------- | ------------- | ----------------- | -------------- | -------------- |
| tool_call_count_p95  | Scores (numeric) | p95(tool_call_count) | > 4         | > 5            |
| latency_e2e_p95      | Observations  | p95(latency)      | > 6s           | > 8s           |
| input_tokens_avg     | Observations  | avg(input_tokens)  | > 6000        | > 8000         |

### 5.3 告警通知渠道

Langfuse v4 Monitors 支持以下通知方式：

| 渠道        | 配置方式                                           | 适用场景       |
| ----------- | -------------------------------------------------- | -------------- |
| Slack       | Langfuse Settings → Integrations → Slack           | 团队即时通知   |
| Webhook     | Langfuse Settings → Integrations → Webhook URL     | 自定义系统对接 |
| GitHub Actions | Langfuse Settings → Integrations → GitHub       | CI/CD 流程联动 |

建议：Slack 作为主告警渠道，Webhook 备用（可对接飞书/企微等）。

### 5.4 Score Analytics

Langfuse v4 的 Score Analytics 面板（Dashboards 页面）：

- Trend Over Time：跟踪各指标随时间的变化趋势
- Distribution：查看 score 值的分布情况
- Compare：对比两个 score 的关联性（如 empty_answer vs tool_whitelist_ok）
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

```python
"""实时规则评估器：每轮问答结束后同步执行，写 Langfuse score。"""

from __future__ import annotations

from typing import Any

from app.core.observability import score_observation
from app.schemas.chat import AssistantResponse, ToolUseBlock, count_tool_use_blocks
from app.utils.logger import logger

# 阈值常量
TOOL_CALL_COUNT_THRESHOLD = 5


def evaluate_and_score(
    *,
    span: Any,
    assistant_response: AssistantResponse,
    agent_mode: int,
    tool_whitelist: set[str],
) -> None:
    """入口函数：计算 P0 指标，写 Langfuse score。失败只告警不冒泡。"""
    try:
        _do_evaluate(
            span=span,
            assistant_response=assistant_response,
            agent_mode=agent_mode,
            tool_whitelist=tool_whitelist,
        )
    except Exception as exc:
        logger.warning("Rule evaluator failed", error=exc, error_type=type(exc).__name__)


def _do_evaluate(
    *,
    span: Any,
    assistant_response: AssistantResponse,
    agent_mode: int,
    tool_whitelist: set[str],
) -> None:
    content = assistant_response.content
    content_blocks = assistant_response.content_blocks

    # --- empty_answer ---
    is_non_empty = len(content.strip()) > 0
    score_observation(span, name="empty_answer", value=is_non_empty)

    # --- tool_whitelist_ok ---
    called_tools = {
        block.name
        for block in content_blocks
        if isinstance(block, ToolUseBlock) and block.name
    }
    if agent_mode <= 0:
        whitelist_ok = len(called_tools) == 0
    else:
        whitelist_ok = called_tools.issubset(tool_whitelist)
    score_observation(
        span,
        name="tool_whitelist_ok",
        value=whitelist_ok,
        comment=f"called={called_tools}" if not whitelist_ok else None,
    )

    # --- tool_call_count ---
    tool_count = count_tool_use_blocks(content_blocks)
    score_observation(span, name="tool_call_count", value=tool_count, data_type="NUMERIC")
```

---

## 七、插入点：chat_orchestrator.py

### 7.1 修改位置

`app/services/chat/chat_orchestrator.py` 的 `run_chat_turn` 方法，正常结束路径（line 522-553）：

```python
# 现有代码 line 522-553：
assistant_response = self.collect_assistant_response()
assistant_updated_at = self.post_process_service.persist_final_assistant_message(...)
await invalidate_conversation_state(...)

# ---- 新增：规则评估 ----
from app.evaluators.rule_evaluator import evaluate_and_score

evaluate_and_score(
    span=root_span,
    assistant_response=assistant_response,
    agent_mode=chat_request.agent_mode,
    tool_whitelist=self._tool_whitelist_cache.get(chat_request.agent_mode, set()),
)
# ---- 新增结束 ----

if trace_enabled and langfuse_client is not None and root_span is not None:
    root_span.update(output=assistant_response.content)
```

### 7.2 白名单缓存

`ChatOrchestrator` 初始化时预计算白名单，避免每轮重复构建：

```python
class ChatOrchestrator:
    def __init__(self, ...):
        ...
        self._tool_whitelist_cache: dict[int, set[str]] = {}
        self._build_tool_whitelists()

    def _build_tool_whitelists(self) -> None:
        """从 MCP gateway 构建各 agent_mode 的工具白名单。"""
        for mode in (0, 1):  # 按实际 agent_mode 范围调整
            whitelist = build_tool_whitelist(mode, self.mcp_gateway)
            self._tool_whitelist_cache[mode] = whitelist
```

如果 MCP 配置热更新，需要在 `reload.py` 的回调中清空缓存重建。

---

## 八、失败与边界处理

| 场景                      | 处理方式                                               |
| ------------------------- | ------------------------------------------------------ |
| 评估函数抛异常             | `logger.warning` 记录，不影响主链路（SSE 流正常返回） |
| Langfuse 未启用           | `score_observation` 内部已处理（span=None 时 no-op）   |
| content_blocks 为空列表   | tool_whitelist_ok=True, tool_call_count=0              |
| ToolUseBlock.name 为 None | 视为未知工具，不加入 called_tools 集合                 |

---

## 九、升级前置条件

本方案依赖 Langfuse v4 的 Monitors & Alerts 功能。

| 检查项                | 当前状态        | 目标状态         |
| --------------------- | --------------- | ---------------- |
| Langfuse 版本         | v3.214.0        | v4.2.0+          |
| Python SDK 版本       | 需确认          | 兼容 v4 的最新版 |
| Monitors & Alerts     | 不可用（v3）    | v4 自托管版支持  |
| Score Analytics       | 不可用（v3）    | v4 支持          |

升级完成后：
1. 在 Langfuse UI 中配置 Monitors（见第五节）
2. 部署 rule_evaluator 代码
3. 观察 1-2 周，确认阈值合理后调整 Monitors 配置

---

## 十、后续扩展（不在本次范围）

1. **离线评估脚本**：从 Langfuse API 拉取 latency_e2e、input_tokens，计算 p95 并写 score
2. **P1 指标接入**：answer_completeness / answer_correctness（LLM-as-Judge，异步 worker）
3. **bad case 回流**：empty_answer=false 或 tool_whitelist_ok=false 的 trace 自动进复核队列
4. **白名单动态更新**：MCP 配置热更新时自动重建白名单缓存
