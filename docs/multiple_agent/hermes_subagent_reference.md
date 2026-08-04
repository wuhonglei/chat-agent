# Hermes Sub-Agent 技术参考

> 基于 Hermes Agent 源码 `tools/delegate_tool.py` 和 `run_agent.py` 整理，记录子 agent 的创建机制、数量限制、输入输出、系统提示词、工具范围等核心设计。

---

## 1. 子 Agent 创建场景

Hermes 提供两种方式创建子 agent：

| 方式 | 适用场景 | 隔离程度 | 持续时间 |
|------|---------|---------|---------|
| `delegate_task` | 快速并行子任务 | 独立对话，共享进程 | 分钟级 |
| 独立 `hermes` 进程 | 长时间自主任务 | 完全独立进程 | 小时/天级 |

### delegate_task 使用场景

- 目标可拆分为 2+ 个独立子任务，可并行执行（如同时调研 A 和 B）
- 子任务推理密集，会产生大量中间数据，会淹没父 agent 上下文
- 需要在隔离环境中执行文件操作，避免污染父 agent 的工作区

### 不适合 delegate_task 的场景

- 单步机械操作 — 直接执行即可
- 一两个工具调用就能完成的 trivial 任务
- 将整个目标原封不动转给一个子 agent — 纯粹的 pass-through，无价值

---

## 2. 子 Agent 数量限制

### 两层防护机制

#### 第一层：单次 delegate_task 调用（delegate_tool.py:2874）

模型在一次 `delegate_task` 调用中传入 `tasks` 列表时，直接校验数量：

```python
max_children = _get_max_concurrent_children()  # 默认 3

if len(tasks) > max_children:
    return tool_error(
        f"Too many tasks: {len(tasks)} provided, but "
        f"max_concurrent_children is {max_children}. "
        f"Either reduce the task count, split into multiple "
        f"delegate_task calls, or increase "
        f"delegation.max_concurrent_children in config.yaml."
    )
```

结果：**直接报错返回**，不执行任何任务。

#### 第二层：同回合多个 delegate_task 调用（run_agent.py:4530）

模型可能在一个回合内发出多个独立的 `delegate_task` tool_call，代码会截断多余的调用：

```python
delegate_count = sum(1 for tc in tool_calls if tc.function.name == "delegate_task")
if delegate_count <= max_children:
    return tool_calls  # 不需要截断

# 保留前 N 个，丢弃多余的，打 warning 日志
kept_delegates = 0
truncated = []
for tc in tool_calls:
    if tc.function.name == "delegate_task":
        if kept_delegates < max_children:
            truncated.append(tc)
            kept_delegates += 1
    else:
        truncated.append(tc)  # 非 delegate 调用保留
```

结果：**静默截断**，保留前 N 个，丢弃多余的，打 warning 日志。

#### 汇总

| 场景 | 行为 |
|------|------|
| 单次调用 tasks > 3 | 返回 tool_error，全部不执行 |
| 同回合多个 delegate_task 调用总数 > 3 | 截断多余的，保留前 3 个 |
| 总数 ≤ 3 | 正常执行 |

配置项：`delegation.max_concurrent_children`（config.yaml，默认 3）。

---

## 3. 限制原因

### 3.1 API Token 成本控制

源码注释（delegate_tool.py:501）：

> each child consumes API tokens

每个子 agent 是一个完整的 agent 循环（系统提示 + 工具调用 + 多轮对话）。3 个并发子 agent 意味着同时消耗 3 份 token 预算。不限制的话，模型一次调用传 10 个 tasks，瞬间烧 10 倍 token。

### 3.2 资源上限

- 每个子 agent 独立的终端会话 + 线程
- 并发 HTTP 请求打 LLM API（rate limit 风险）
- 文件系统竞争（git 冲突、文件锁）

### 3.3 上下文管理

子 agent 完成后要把摘要塞回父 agent 的上下文。5 个子 agent 的返回结果同时灌入，可能直接触发 context compression，反而丢失关键信息。

### 3.4 防止模型"偷懒"

模型倾向于一次性把任务拆成很多小 task 并行派发。但实际执行中：
- 并行子 agent 之间无法通信
- 各自独立上下文，容易产生冲突代码
- 越多越难协调质量

限制逼迫模型精选最有价值的并行任务，而不是"撒胡椒面"。

### 3.5 设计哲学

Hermes 的设计哲学是"保守核心、激进边缘"。delegate_task 作为核心工具，默认保守限制，用户按需放开。这是一种**安全默认值**策略。

---

## 4. delegate_task 输入输出

### 4.1 输入（Input）

支持两种调用模式：

#### 模式一：单任务（goal）

```json
{
  "goal": "具体任务描述",
  "context": "背景信息：文件路径、错误消息、项目结构、约束条件",
  "role": "leaf | orchestrator"
}
```

#### 模式二：批量任务（tasks）

```json
{
  "tasks": [
    {"goal": "任务1", "context": "...", "role": "leaf"},
    {"goal": "任务2", "context": "...", "role": "orchestrator"}
  ],
  "role": "leaf | orchestrator"
}
```

#### 输入字段说明

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `goal` | string | 是（单任务模式） | 子 agent 要完成的任务，必须自包含（子 agent 不知道父的对话历史） |
| `context` | string | 否 | 背景信息（文件路径、错误消息、项目结构、约束） |
| `tasks` | array | 是（批量模式） | 批量任务列表，每个元素同上 |
| `role` | enum | 否 | `leaf`（默认，不能再派生）或 `orchestrator`（可以继续派生） |
| `background` | bool | 否 | 已废弃，自动后台执行，参数保留仅为兼容 |

### 4.2 输出（Output）

返回 JSON 字符串，结构如下（delegate_tool.py:3149）：

```json
{
  "results": [
    {
      "task_index": 0,
      "status": "completed",
      "summary": "子 agent 的执行摘要（截断至 500 字符）",
      "api_calls": 5,
      "duration_seconds": 42.3,
      "model": "mimo-v2.5-pro",
      "exit_reason": "completed",
      "tokens": {
        "input": 12000,
        "output": 3000
      },
      "tool_trace": ["terminal", "read_file", "write_file"],
      "live_transcript": "/path/to/task-0.log"
    }
  ],
  "total_duration_seconds": 45.2,
  "live_transcripts": ["/path/to/task-0.log"]
}
```

#### 成功条目字段

| 字段 | 说明 |
|------|------|
| `task_index` | 任务序号（对应输入顺序） |
| `status` | `completed` / `failed` / `error` / `interrupted` |
| `summary` | 子 agent 的最终回复摘要（超长会截断 + spill 到磁盘） |
| `api_calls` | 子 agent 调用 LLM 的次数 |
| `duration_seconds` | 执行耗时 |
| `model` | 使用的模型 |
| `exit_reason` | 退出原因 |
| `tokens.input/output` | token 消耗 |
| `tool_trace` | 使用过的工具列表 |
| `live_transcript` | 实时日志文件路径（可 `tail -f` 监控） |

#### 错误条目字段

```json
{
  "task_index": 0,
  "status": "error",
  "summary": null,
  "error": "具体错误信息",
  "api_calls": 0,
  "duration_seconds": 0
}
```

#### 被截断条目字段（父 agent 中断时）

```json
{
  "task_index": 0,
  "status": "interrupted",
  "summary": null,
  "error": "Parent agent interrupted — child did not finish in time",
  "api_calls": 0,
  "duration_seconds": 0
}
```

### 4.3 关键行为

- **异步执行**：父 agent 不阻塞，所有子 agent 完成后一起返回
- **摘要截断**：summary 限制 500 字符，超出部分 spill 到磁盘文件
- **结果排序**：按 task_index 排序，保证与输入顺序一致
- **实时监控**：每个子 agent 有独立的 live transcript 日志文件

---

## 5. 子 Agent 的系统提示词

定义在 `_build_child_system_prompt`（delegate_tool.py:789），是一段**精简的专用提示**，不是父 agent 的系统提示。

### 5.1 基础提示词（所有角色共享）

```
You are a focused subagent working on a specific delegated task.

YOUR TASK:
{goal}

CONTEXT:
{context}

WORKSPACE PATH:
{workspace_path}
Use this exact path for local repository/workdir operations unless the task
explicitly says otherwise.

Complete this task using the tools available to you. When finished, provide a
clear, concise summary of:
- What you did
- What you found or accomplished
- Any files you created or modified
- Any issues encountered

Important workspace rule: Never assume a repository lives at /workspace/... or
any other container-style path unless the task/context explicitly gives that
path. If no exact local path is provided, discover it first before issuing
git/workdir-specific commands.

Keep your final summary tight: lead with outcomes, prefer bullet points over
paragraphs, and don't replay your whole process. Your response is returned to
the parent agent as a summary, and overlong summaries crowd out the parent's
context window.
```

### 5.2 Orchestrator 角色额外提示词

如果角色是 `orchestrator`，追加一段子 agent 派生指南：

```
## Subagent Spawning (Orchestrator Role)

You have access to the `delegate_task` tool and CAN spawn your own subagents
to parallelize independent work.

WHEN to delegate:
- The goal decomposes into 2+ independent subtasks that can run in parallel
  (e.g. research A and B simultaneously).
- A subtask is reasoning-heavy and would flood your context with intermediate
  data.

WHEN NOT to delegate:
- Single-step mechanical work — do it directly.
- Trivial tasks you can execute in one or two tool calls.
- Re-delegating your entire assigned goal to one worker (that's just
  pass-through with no value added).

Coordinate your workers' results and synthesize them before reporting back to
your parent. You are responsible for the final summary, not your workers.

NOTE: You are at depth {child_depth}. The delegation tree is capped at
max_spawn_depth={max_spawn_depth}.
```

### 5.3 深度限制

- `max_spawn_depth` 默认 2（可通过 `delegation.max_spawn_depth` 配置）
- 当 `child_depth + 1 >= max_spawn_depth` 时，orchestrator 的子 agent 强制降级为 leaf，不能再派生

---

## 6. 子 Agent 的工具范围

### 6.1 继承规则

子 agent 继承父 agent 的 enabled_toolsets，但有严格的裁剪逻辑：

1. **继承父 agent 的 enabled_toolsets** — 子 agent 不能拥有父 agent 没有的工具
2. **移除完全被阻止的 toolset** — 如果一个 toolset 的所有工具都在 blocked 列表中，整个移除
3. **从混合 toolset 中禁止单个工具** — 如 `hermes-cli` 包含多个工具，只移除其中被阻止的
4. **orchestrator 角色例外** — 保留 `delegate_task` 工具，允许继续派生
5. **kanban 始终移除**

### 6.2 被禁止的工具（DELEGATE_BLOCKED_TOOLS）

```python
DELEGATE_BLOCKED_TOOLS = frozenset([
    "delegate_task",    # 默认禁止递归（orchestrator 角色除外）
    "clarify",          # 不能与用户交互
    "memory",           # 不能写共享 MEMORY.md
    "send_message",     # 不能跨平台发消息
    "cronjob",          # 不能以父 agent 名义调度任务
])
```

### 6.3 角色与工具对照

| 角色 | 可用工具 |
|------|---------|
| leaf（默认） | 父 agent 的所有工具，减去 delegate_task / clarify / memory / send_message / cronjob |
| orchestrator | 同上 + delegate_task（可继续派生子 agent） |

### 6.4 其他关键配置

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `skip_memory` | True | 子 agent 不读写持久化记忆 |
| `skip_context_files` | True | 子 agent 不加载 AGENTS.md / CLAUDE.md 等上下文文件 |
| `ephemeral_system_prompt` | 子 agent 专用提示词 | 不继承父 agent 的系统提示 |
| `quiet_mode` | True | 子 agent 静默运行 |
| `clarify_callback` | None | 子 agent 不能向用户提问 |
| `max_iterations` | 50（delegation.max_iterations） | 每个子 agent 独立的迭代预算 |

---

## 7. 子 Agent 完整属性总览

| 维度 | 子 agent 行为 |
|------|--------------|
| 系统提示词 | 专用精简版，不是父 agent 的提示词 |
| 工具 | 继承父 agent，移除 5 个禁止工具 |
| Skills | 不加载 |
| Memory | 不读写 |
| AGENTS.md | 不加载 |
| 模型 | 默认继承父 agent，可通过 delegation config 覆盖 |
| 迭代次数 | 独立预算，默认最大 50 次 |
| 用户交互 | 禁止（clarify 被禁，无 clarify_callback） |
| 通信方式 | 单向：父传 goal + context → 子返回 summary |
| 并发执行 | 使用 DaemonThreadPoolExecutor，主线程不阻塞 |
| 中断传播 | 父 agent 中断时，向所有子 agent 发送中断信号 |

---

## 8. 执行流程简述

```
父 Agent 调用 delegate_task
  ↓
校验任务数量 ≤ max_concurrent_children
  ↓
为每个子任务构建独立的 AIAgent
  - 继承父 agent 的 provider / model / credentials
  - 生成专用系统提示词（goal + context）
  - 裁剪工具集（移除 blocked tools）
  - 跳过 memory / context_files / skills
  ↓
所有子 agent 并行执行（DaemonThreadPoolExecutor）
  - 每个子 agent 有独立的迭代预算
  - 每个子 agent 有实时日志 transcript
  - 心跳机制保持父 agent 活跃（防止 gateway 超时）
  ↓
所有子 agent 完成后聚合结果
  - 按 task_index 排序
  - 截断过长的 summary（spill 到磁盘）
  - 返回统一的 JSON 结果给父 agent
```

---

## 相关源码位置

| 内容 | 文件路径 |
|------|---------|
| delegate_task 入口 + 调度逻辑 | `tools/delegate_tool.py` |
| 系统提示词构建 | `delegate_tool.py::_build_child_system_prompt` (L789) |
| 子 agent 构建 | `delegate_tool.py::_build_child_agent` (L1194) |
| 工具裁剪 | `delegate_tool.py::_strip_blocked_tools` (L894) |
| 禁止工具列表 | `delegate_tool.py::DELEGATE_BLOCKED_TOOLS` (L48) |
| 结果聚合 | `delegate_tool.py::_execute_and_aggregate` (L2978) |
| 单子 agent 执行 | `delegate_tool.py::_run_single_child` (L1965) |
| 同回合截断逻辑 | `run_agent.py::_cap_delegate_task_calls` (L4530) |
| schema 定义 | `delegate_tool.py::DELEGATE_TASK_SCHEMA` (L3773) |
