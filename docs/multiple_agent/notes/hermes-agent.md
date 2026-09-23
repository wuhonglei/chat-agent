# Hermes Agent 多 Agent / 子 Agent（delegate_task 子代理）实现分析

> 分析对象：`/Users/apple/.hermes/hermes-agent`（Hermes Agent，Python）
> 核心实现集中在 `tools/delegate_tool*.py`（由原 `delegate_tool.py` 拆分出的兄弟模块）、`tools/async_delegation.py`、`tools/delegation_output_schema.py`、`agent/delegation_context.py`、`agent/subagent_lifecycle.py`。
> 顶层架构一句话（`tools/delegate_tool.py:3-12` 模块 docstring）："Spawns child AIAgent instances with a fresh conversation, their own task_id (terminal session, file-ops cache), the parent's toolsets minus child-blocked tools, and a focused system prompt built from goal + context… The parent only ever sees the delegation call and the summary result, never the child's intermediate tool calls or reasoning."

---

## 1. 创建子 agent 的时机

### 结论

子 agent 由 **工具调用触发**：模型调用 `delegate_task` 工具（注册于 `delegation` toolset），运行时拦截点是 `run_agent.AIAgent._dispatch_delegate_task`。另有两个非模型入口复用同一套子代理生命周期：`/review` 代码审查（`agent/review_engine.py` 直接调 `delegate_task(...)`）和插件 API `agent/subagent_lifecycle.py`（`PluginContext.subagent_lifecycle.launch()`）。**cron/kanban 调度并不会自动派生子 agent**——cron 任务只是把通道声明为 stateless，让任务内部的 `delegate_task` 走同步内联路径（`cron/scheduler.py:2259-2268`）。派生前有多道闸门：全局 pause 开关（`is_spawn_paused()`）、深度上限（`max_spawn_depth`）、一次性会话预算（`oneshot_max_children`）。

### 证据

- `tools/delegate_tool.py:736-750` — 工具注册（入口工具名 `delegate_task`）：
  ```python
  registry.register(
      name="delegate_task",
      toolset="delegation",
      schema=DELEGATE_TASK_SCHEMA,
      handler=lambda args, **kw: delegate_task(...),
  ```
- `tools/delegate_tool.py:439-449` — 主入口函数：
  ```python
  def delegate_task(goal=None, context=None, tasks=None, ..., action=None, subagent_id=None, message=None, parent_agent=None, ...):
      """Spawn child agents (single ``goal`` or ``tasks=[...]`` batch) or control running ones."""
  ```
- `run_agent.py:1347-1360` — 模型工具调用的唯一派发点；顺带规定顶层派生强制后台、子 agent 内派生强制同步：
  ```python
  def _dispatch_delegate_task(self, function_args: dict) -> str:
      # Top-level MODEL delegations always run in the background … An ORCHESTRATOR SUBAGENT (depth > 0) stays synchronous …
      return _delegate_task(..., background=not (getattr(self, "_delegate_depth", 0) > 0), ...)
  ```
- `tools/delegate_tool.py:453-464` — 同一工具兼作控制面（`action=list/steer/stop`）+ pause 杀开关：
  ```python
  if normalized_action in _CONTROL_ACTIONS:
      return _handle_control_action(...)
  if is_spawn_paused():
      return tool_error("Delegation spawning is paused. …")
  ```
- `tools/delegate_tool.py:471-478` — 派生前深度闸门：
  ```python
  if depth >= max_spawn:
      return tool_error(f"Delegation depth limit reached (depth={depth}, max_spawn_depth={max_spawn})…")
  ```
- `agent/review_engine.py:170-171` — 非模型内部调用（/review）：
  ```python
  from tools.delegate_tool import delegate_task
  raw = delegate_task(goal=goal, context=context, background=True, parent_agent=parent_agent, credentials_cfg=credentials_cfg)
  ```
- `agent/subagent_lifecycle.py:245-248` — 插件 API 入口（`SubagentLaunchRequest` → `_run_child_lifecycle`，见 `:366-367`）：
  ```python
  def launch(self, request: SubagentLaunchRequest) -> SubagentHandle:
      parent = self._parent_agent_resolver()
      if parent is None:
          raise SubagentLifecycleError("No active Hermes parent session is available.")
  ```
- `cron/scheduler.py:2259-2267` — cron 不派生子 agent，只把 delegate_task 收敛为同步内联：
  ```
  # Declaring the channel stateless routes delegate_task to its existing inline/synchronous path,
  # so results return within the job's own turn. …
  async_delivery=False,
  ```

---

## 2. 子 agent 的上下文管理

### 结论

子 agent 拿到的是**全新会话**（fresh conversation），不继承父的对话历史与系统提示词；系统提示词用 goal+context 现场构造（goal 作为子 agent 的第一条 user 消息）。显式隔离项：`skip_memory=True`（不读共享 MEMORY.md）、`skip_context_files=True`（但会按主 agent 同样规则把工作区项目上下文文件 AGENTS.md/CLAUDE.md 等注入子提示词，跳过 SOUL.md——身份属于父）、独立 task_id（终端会话/file-ops 缓存）、独立但同库的 SessionDB 句柄（保留 `parent_session_id` 血缘用于 lineage/session_search）、Kanban worker 身份环境变量被擦除（`scrub_kanban_env`）、可选 git worktree 隔离。继承项：`prefill_messages`、父工具集（见第 5 节）、模型/凭证（或 delegation 配置覆盖）、credential pool 共享。结果回传是**摘要制**：父只拿到子的 `final_response`（作为 `summary`），有摘要预算裁剪（超限 75%头+25%尾、全文 spill 到磁盘并给出 read_file 指针），子的中间工具调用/推理不回传（只有脱敏的 tool_trace 元数据）。

### 证据

- `tools/delegate_tool.py:236-248` — 子 AIAgent 构造（隔离要点集中在此）：
  ```python
  child = AIAgent(
      **rt, max_iterations=max_iterations, prefill_messages=getattr(parent_agent, "prefill_messages", None),
      enabled_toolsets=child_toolsets, disabled_toolsets=child_disabled_toolsets, quiet_mode=True,
      ephemeral_system_prompt=child_prompt, log_prefix=f"[subagent-{task_index}]", platform="subagent",
      skip_context_files=True, skip_memory=True, clarify_callback=None,
      ...
      session_db=child_session_db, parent_session_id=parent_sid, ...)
  ```
- `tools/delegate_tool.py:5-11` — 隔离契约 docstring："Spawns child AIAgent instances with a fresh conversation, their own task_id (terminal session, file-ops cache) … The parent only ever sees the delegation call and the summary result, never the child's intermediate tool calls or reasoning."
- `tools/delegate_tool_progress.py:185-208` — goal 是子的第一条 user 消息；工作区上下文文件补注入：
  ```python
  # The goal is the child's first user turn (see ``_ChildRun.await_child``).
  ...
  # Project context files (AGENTS.md / CLAUDE.md / .cursorrules ...) via the SAME discovery/priority/cap logic
  # as the main agent's prompt: children are built with skip_context_files=True, so without this a subagent
  # works in a repo blind to its conventions. SOUL.md is skipped (identity belongs to the parent).
  _ctx_files = build_context_files_prompt(cwd=str(workspace_path), skip_soul=True)
  ```
- `tools/delegate_tool.py:85-106` — 子用独立 SessionDB 句柄、同库文件保血缘：
  ```python
  def _open_child_session_db(parent_agent) -> Any:
      """DEDICATED SessionDB handle for the child … It MUST open the same db FILE as the parent's
      handle (non-launch profiles), else lineage / session_search break"""
  ```
- `tools/delegate_tool_child_run.py:748-772` — `seed_workspace`：子 task_id 播种父 cwd/容器别名、可选 worktree 隔离（goal 追加隔离契约说明）：
  ```python
  record_session_cwd(self.child_task_id, get_session_cwd(self.parent_task_id))
  register_container_alias(self.child_task_id, self.parent_task_id)
  self.worktree_info = _create_isolated_worktree(...)
  ```
- `agent/delegation_context.py:102-118` — `scrub_kanban_env`：子进程/后代继承环境时擦除 `HERMES_KANBAN_*` worker 身份并打 `HERMES_DELEGATED_CHILD_CONTEXT` 标记（Kanban 写围栏，`:121-142`）。
- 结果回传（摘要 + 预算裁剪 + spill）：
  - `tools/delegate_tool_results.py:158-166`：
    ```python
    DEFAULT_MAX_SUMMARY_CHARS = 24000
    _SUMMARY_HEADROOM_FRACTION = 0.5
    _MIN_SUMMARY_CHARS = 2000
    ```
  - `tools/delegate_tool_results.py:187-223` `_trim_summary_with_footer`："a ~75% head / ~25% tail window … the full text spilled to disk, and a footer giving the exact ``read_file offset=`` for the omitted middle."
  - `tools/delegate_tool_results.py:266-294` `_apply_summary_budget`："Trim subagent summaries in-place so a batch can't overflow the parent's context window (full text spilled to disk)"，裁剪后置 `summary_truncated=True`、`summary_full_path`。
  - `tools/delegate_tool_results.py:330-343` `_notify_memory_manager`：子结果经 `memory.on_delegation(task=…, result=…, child_session_id=…)` 进父的记忆管理器（父侧记录，非子写 MEMORY.md）。
- 工具调用轨迹只回传脱敏元数据：`tools/delegate_tool_child_run.py:521-551` `_build_tool_trace`（只记 tool 名、`args_bytes`、`input_summary`、`result_bytes`、ok/error）；输入摘要脱敏见 `tools/delegate_tool_results.py:124-132` `_summarize_tool_arguments`（"Summarize argument names and side-effect targets without raw payloads"）。

---

## 3. 子 agent 的输入输出内容

### 结论

输入是 JSON Schema `DELEGATE_TASK_SCHEMA`：`tasks=[{goal(必填), context, output_schema, images(≤8), group}]` 数组（一项=一个子 agent，多项=并行扇出），顶层还有 `action/subagent_id/message` 控制字段；遗留单任务形状 `goal/context/output_schema/images/max_iterations/role` 仍被接受并包装成单项批（故意不对模型宣传）。`goal` 质量有批级校验（拒绝 `TODO`/未展开模板标记/多任务下 <10 字符的 goal）。`output_schema`（JSON Schema）会以 OUTPUT CONTRACT 块附加到子的 context，父用 jsonschema 校验最终答复，失败仅做**一次**有界重试。输出同步路径是 JSON `{"results": [entry…], "total_duration_seconds", …}`，每条 entry 含 `task_index/status(completed|interrupted|failed)/summary/exit_reason/truncated/api_calls/duration_seconds/model/tokens/tool_trace/cost_usd/…` 及可选 `schema_valid/schema_errors/schema_note`、`error/failure_reason`、`missed_steer`、`worktree`、`orphaned_processes` 等；后台路径先返回 dispatch handle（`status:"dispatched"` + `subagent_ids` + `live_transcripts` + control_hint），完成后结果以新消息再次进入对话。

### 证据

- 输入 schema：`tools/delegate_tool.py:633-713` `DELEGATE_TASK_SCHEMA`，关键摘录：
  ```python
  "tasks": {"type": "array", "minItems": 1, "items": {"type": "object", "properties": {
      "goal": _p("string", "What this subagent should accomplish. Be specific and self-contained — it knows nothing about your conversation history."),
      "context": _p("string", "Background THIS child needs: file paths, error messages, constraints. …"),
      "output_schema": _p("object", "Optional JSON Schema this child's final answer must validate against (told to the child up front; parent validates with one bounded correction retry; …"),
      "images": _p("array", "Optional images this child must SEE (max 8): local file paths or http(s) URLs …", items={"type": "string"}),
      "group": _p("string", "Optional result-delivery bucket within this call (only when delegation.independent_completions is enabled; …)"),
  }, "required": ["goal"]},
  "action": _p("string", "Default 'spawn'. Live control of running children: 'list' … 'steer' … 'stop' …", enum=["spawn", "list", "steer", "stop"]),
  ```
  （遗留顶层 `goal/context/output_schema/images` 与被忽略的 `background` 见 `:645-648`、`:692-693` 注释 "unadvertised on purpose … do not re-add"。）
- 任务归一化/校验：`tools/delegate_tool_tasks.py:67-105` `_normalize_task_list`；批级质量门 `:36-65` `_validate_batch_tasks`（`_PLACEHOLDER_GOAL_RE`/`_TEMPLATE_MARKER_RE`/`_MIN_BATCH_GOAL_LEN = 10`）；数量超限报错 `:81-86`（"Too many tasks … max_concurrent_children is {max_children}"）。图片 `:124-147`（`_MAX_TASK_IMAGES = 8`）；schema 元校验 `:107-122` `_coerce_task_schemas`。
- OUTPUT CONTRACT 注入：`tools/delegation_output_schema.py:45-57`：
  ```python
  block = ("OUTPUT CONTRACT (machine-validated):\n"
           "Your FINAL response must be ONLY the JSON value that validates against this JSON "
           "Schema — no prose before or after it, no code fence, no explanation. …")
  ```
- 一次有界重试：`tools/delegation_output_schema.py:109-115` `build_retry_message`（"Single bounded retry turn: errors verbatim, schema deliberately NOT re-pasted"）；执行在 `tools/delegate_tool_child_run.py:479-519` `_validate_child_output_schema`（"Exactly one retry turn"）。
- 输出 entry 组装：`tools/delegate_tool_child_run.py:553-650` `_build_result_entry`：
  ```python
  entry = {"task_index": …, "status": status, "summary": summary, "api_calls": …, "duration_seconds": duration,
           "model": …, "exit_reason": exit_reason, "truncated": exit_reason == "max_iterations",
           "tokens": {...}, "tool_trace": _build_tool_trace(result.get("messages") or []), ...}
  ```
  schema 失败不丢弃原始文本（`:580-586` 注释："the child's raw final text is the deliverable … `schema_valid: false` + `schema_errors` carry the contract verdict"）。
- 结果契约 status/exit_reason：`tools/delegate_tool.py:298-313` `_run_single_child` docstring："status ∈ {completed, interrupted, failed} … exit_reason ∈ {completed, max_iterations, interrupted, error} … truncated == (exit_reason == \"max_iterations\")"。
- 同步总包：`tools/delegate_tool_dispatch.py:206-217` `combined = {"results": results, "total_duration_seconds": total_duration}`（+ `process_notes`/`live_transcripts`/`group`）。
- 后台 dispatch handle：`tools/delegate_tool_dispatch.py:344-365` `_dispatched_payload`（`{"status": "dispatched", "mode": "background", "count": n, "delegation_id": …, "goals": […], "note": …, "subagent_ids": […], "control_hint": …, "live_transcripts": […]}`）。

---

## 4. 子 agent 的系统提示词

### 结论

构造函数在 `tools/delegate_tool_progress.py:178-217` `_build_child_system_prompt`（经 `tools/delegate_tool.py:203-206` 调用），通过 `ephemeral_system_prompt` 传入子 AIAgent。核心结构：一句身份行 + `CONTEXT:`（父传的 context，含 OUTPUT CONTRACT）+ `WORKSPACE PATH:` + 工作区项目上下文文件（AGENTS.md 等，跳过 SOUL.md）+ 完成指令（要求简短 final summary，明确"你的回复作为 summary 返回父 agent"）+ orchestrator 角色追加的「Subagent Spawning」授权块与深度说明。goal 不进系统提示词，作为子的第一条 user 消息（避免 Anthropic OAuth 同一任务双角色发送）。

### 证据

- `tools/delegate_tool_progress.py:188-209` — 主体：
  ```python
  parts = ["You are a focused subagent working on a specific delegated task."]
  if context and context.strip():
      parts.append(f"\nCONTEXT:\n{context}")
  if workspace_path and str(workspace_path).strip():
      parts.append("\nWORKSPACE PATH:\n" f"{workspace_path}\n" "Use this exact path for local repository/workdir operations …")
      … _ctx_files = build_context_files_prompt(cwd=str(workspace_path), skip_soul=True) …
  parts.append(_COMPLETION_INSTRUCTIONS)
  ```
- `tools/delegate_tool_progress.py:146-155` — 完成指令（final summary 契约）：
  ```python
  _COMPLETION_INSTRUCTIONS = (
      "\nComplete this task using the tools available to you. When finished, provide a clear, concise summary of:\n"
      "- What you did\n- What you found or accomplished\n- Any files you created or modified\n- Any issues encountered\n\n"
      "Important workspace rule: Never assume a repository lives at /workspace/... …\n\n"
      "Keep your final summary tight: lead with outcomes … Your response is returned to the parent agent as a summary, and overlong summaries crowd out the parent's context window.")
  ```
- `tools/delegate_tool_progress.py:156-168` — orchestrator 追加块：
  ```python
  _ORCHESTRATOR_BLOCK = (
      "\n## Subagent Spawning (Orchestrator Role)\n"
      "You have access to the `delegate_task` tool and CAN spawn your own subagents to parallelize independent work.\n\n"
      "WHEN to delegate: … WHEN NOT to delegate: … "
      "Coordinate your workers' results and synthesize them before reporting back to your parent. …")
  ```
- `tools/delegate_tool_progress.py:210-216` — 深度真值注记（防止模型臆造嵌套能力）：
  ```python
  child_note = _LEAF_CHILDREN_NOTE if child_depth + 1 >= max_spawn_depth else _NESTED_CHILDREN_NOTE
  parts.append(_ORCHESTRATOR_BLOCK + f"NOTE: You are at depth {child_depth}. The delegation tree is capped at max_spawn_depth={max_spawn_depth}. " + child_note)
  ```
- goal 作 user 首条消息：`tools/delegate_tool_progress.py:185-187` 注释 + `tools/delegate_tool_child_run.py:850-860`（`user_message = _build_child_goal_message(...) if _images else self.goal` → `child.run_conversation(user_message=…)`）。

---

## 5. 子 agent 的工具范围

### 结论

工具集**继承父级再做减法**（"the parent's toolsets minus child-blocked tools"）：默认整个父工具集原样传入（`toolsets=None`，schema 里没有 toolsets 参数，模型无法指定），并遵守父的 disabled_toolsets。硬禁用名单 `DELEGATE_BLOCKED_TOOLS = {delegate_task, clarify, memory, send_message, cronjob_manage}`，外加整套移除 `delegation`、`kanban` toolset，且用 disabled_toolsets 在混合 bundle（如 hermes-cli）复合展开后精确减去被禁名字。**深度限制**：默认 `max_spawn_depth=1`（扁平，子不能再派孙）；`delegation.max_spawn_depth` 可调高（无硬顶），role 不是模型参数而是按深度派生——只有 `orchestrator_enabled=True` 且 `child_depth < max_spawn_depth` 的子拿回 `delegate_task`（`delegation` toolset 重新加入）成为 orchestrator，否则一律 leaf。

### 证据

- 禁用名单：`tools/delegate_tool_toolsets.py:14-22`：
  ```python
  DELEGATE_BLOCKED_TOOLS = frozenset(
      ["delegate_task",  # no recursive delegation
       "clarify",  # no user interaction
       "memory",  # no writes to shared MEMORY.md
       "send_message",  # no cross-platform side effects
       "cronjob_manage",  # no scheduling more work in the parent's name
      ])
  ```
- 继承父集 + 精确减法：`tools/delegate_tool.py:390-391`（`toolsets=None,  # always inherit the parent's toolsets`）；`tools/delegate_tool_toolsets.py:77-123` `_resolve_child_toolsets`：
  ```python
  # Children never gain tools the parent lacks … Blocked tools are stripped twice — whole blocked toolsets here,
  # and exact one-tool deny toolsets via ``disabled_toolsets`` … Orchestrators get ``delegation`` re-added unconditionally
  ...
  child_disabled_toolsets = list(dict.fromkeys(inherited_disabled + _blocked_toolsets_for_role(effective_role) + ["kanban"]))
  ```
- `delegation`/`kanban` 整套剔除：`tools/delegate_tool_toolsets.py:56-65` `_strip_blocked_tools`："composite toolsets children must never get (``delegation``, ``kanban``)"。
- 深度派生 role（模型不可控）：`tools/delegate_tool.py:59-69`（`role` "legacy … capability is depth-derived"）+ `:187-191`：
  ```python
  child_depth = getattr(parent_agent, "_delegate_depth", 0) + 1
  max_spawn = _get_max_spawn_depth()
  effective_role = "orchestrator" if _get_orchestrator_enabled() and child_depth < max_spawn else "leaf"
  ```
- 默认扁平：`tools/delegate_tool_config.py:21-22`（`MAX_DEPTH = 1  # flat by default: parent (0) -> child (1); deeper needs max_spawn_depth`）；`:151-163` `_get_max_spawn_depth`（floor 1，"no ceiling"，默认 MAX_DEPTH=1）；kill switch `:165-173` `_get_orchestrator_enabled`（default True，False 强制全员 leaf）。
- 模型可见的限制说明：`tools/delegate_tool.py:546-552`（"Children cannot call delegate_task, clarify, memory, or cronjob." / orchestrator 可用时改为 "Children can themselves delegate while depth remains"）。
- 公开插件 API 也有 blocked_tools/allowed_toolsets 字段：`agent/subagent_lifecycle.py:54-55`（`SubagentLaunchRequest.allowed_toolsets / blocked_tools`）。

---

## 6. 子 agent 的运行方式

### 结论

分两条路径：**模型顶层派生默认后台异步**（`run_agent.py:1357` 强制 `background=not (depth>0)`，schema 的 `background` 参数被故意忽略）——dispatch 立即返回 handle，完成后以 `type="async_delegation"` 事件进共享 `process_registry.completion_queue`，在**回合之间**作为新消息重新进入父会话；**orchestrator 子 agent 的再派生同步阻塞**（在自己回合内 join 自己的 worker）。会话不能接收延迟结果（one-shot CLI/cron/stateless HTTP）或后台池满时自动降级为同步内联并附 note。并发：批内并行 `DaemonThreadPoolExecutor(max_workers=max_children)`，上限 `delegation.max_concurrent_children`（默认 10，只有 ≥1 下限无上限，>10 有成本告警）；后台池同上限且**满则拒绝不排队**（调用方转同步）；一次性会话另有 `delegation.oneshot_max_children`（默认 2，总量）。超时：默认**无墙钟超时**（`DEFAULT_CHILD_TIMEOUT = None`，卡死靠心跳陈旧判定：空闲 450s / 工具内 1200s 放弃等待）；可选 `delegation.child_timeout_seconds` 是**无进展**预算（≥30s，任何进展重置，80% 处经 steer 通道预警一次）。后台陈旧监控同阈值（30s 采样、120s 宽限后强制 `stalled` 终结）。控制面：同一工具 `action=list/steer/stop`（同步执行、绕过 pause/深度闸门），steer 把文本追加到子下一个工具结果（不打断当前工具调用），stop 走 cooperative hard interrupt 并递归孙代；另有 TUI/RPC 同源注册表（`tui_gateway/methods_subagents.py`）。

### 证据

- 顶层强制后台 / 子内强制同步：`run_agent.py:1350-1357`（摘录见第 1 节）；镜像实现 `tools/delegate_tool.py:719-725` `_model_background_value`："Top-level delegations always run in the background — the model does not choose … an orchestrator subagent (depth > 0) is the exception"。
- 批内并行线程池：`tools/delegate_tool_dispatch.py:143-150`：
  ```python
  executor = DaemonThreadPoolExecutor(max_workers=batch.max_children)
  futures = {executor.submit(contextvars.copy_context().run, batch.run_child, i, t, child): i for i, t, child in batch.children}
  ```
  单任务直跑 `:187-191`；聚合 `_execute_and_aggregate` `:180-217`。
- 并发上限：`tools/delegate_tool_config.py:17`（`_DEFAULT_MAX_CONCURRENT_CHILDREN = 10`）+ `:93-108` `_get_max_concurrent_children`（"delegation.max_concurrent_children > DELEGATION_MAX_CONCURRENT_CHILDREN env > 10 … Floor of 1 is the only bound enforced; there is no ceiling"）。一次性预算 `:85-90`（`oneshot_max_children`，默认 2）与 `tools/delegate_tool.py:419-436` `_oneshot_spawn_budget`（超限错误文案要求模型自己内联完成）。
- 后台池容量拒绝不排队：`tools/async_delegation.py:561-565` `_dispatch_admitted`："Capacity check + record insert happen under ONE lock hold … At capacity the dispatch is REJECTED (never queued) so a runaway model can't pile up unbounded background work."；容量即 `max_concurrent_children`：`tools/delegate_tool_config.py:121-132` `_get_max_async_children`（"`delegation.max_async_children` is deprecated and ignored; `delegation.max_concurrent_children` now caps background delegations too"）。拒绝后同步回退：`tools/delegate_tool_dispatch.py:451-456`（`_run_sync_with_note(batch, "at_capacity")`）+ `:219-231` `_SYNC_FALLBACK_NOTES`（"The background delegation pool was at capacity … ran SYNCHRONOUSLY"）。
- 同步降级（无异步消费者）：`tools/delegate_tool_dispatch.py:240-274` `_resolve_async_wake_sid`（"Finite sessions cannot route a detached subagent result back … Fall back to SYNCHRONOUS execution"）；提示语 `:321-342` `_BACKGROUND_NOTES`（"Results are delivered only after you END YOUR TURN … Do not poll its transcript"）。
- 超时默认关闭：`tools/delegate_tool_config.py:24-27`：
  ```python
  # No default wall-clock cap on children: legitimate heavy work … was being killed mid-task. Stuck-child detection is the heartbeat staleness monitor;
  # delegation.child_timeout_seconds opts back in.
  DEFAULT_CHILD_TIMEOUT: Optional[float] = None
  ```
  无进展预算 `:134-149` `_get_child_timeout`（"Inactivity cap for one child (seconds of NO progress) … floor 30 s"）；预算预警 `tools/delegate_tool_child_run.py:228-246`（`_BUDGET_WARNING_FRACTION = 0.8`，`_warn_child_budget` 经 `child.steer(...)` 投递）；等待循环 `:790-826` `wait_liveness_aware`。
- 心跳陈旧判定：`tools/delegate_tool.py:72-78`（`_HEARTBEAT_INTERVAL = 30`、`_HEARTBEAT_STALE_CYCLES_IDLE = 15  # 450s idle`、`_HEARTBEAT_STALE_CYCLES_IN_TOOL = 40  # 1200s stuck on same tool`）；放弃等待 `tools/delegate_tool_child_run.py:316-331`（"Subagent %d appears stale … abandoning its wait"）。后台侧镜像阈值 `tools/async_delegation.py:59-62`（`_STALE_CHECK_INTERVAL = 30.0`、`_STALE_IDLE_SECONDS = 450.0`、`_STALE_IN_TOOL_SECONDS = 1200.0`、`_STALL_GRACE_SECONDS = 120.0`）。
- 结果通知回父（后台）：`tools/async_delegation.py:2-8`："On completion a ``type=\"async_delegation\"`` event … is pushed onto the SHARED ``process_registry.completion_queue`` the CLI/gateway drain while idle, so results surface as a NEW turn (never mid-turn) and inherit its de-dup and crash-recovery wiring."；事件体 `:262-267`（`"type": "async_delegation", "delegation_id": …, "session_key": …, "goals": …` 等）；组内单任务先失败即时通知 `tools/delegate_tool_dispatch.py:164-173`（`push_task_failure_notice`）；持久账本与投递上限 `tools/async_delegation.py:43-49`（`_MAX_DELIVERY_ATTEMPTS = 8`、`_MAX_COMPLETION_REPLAY_AGE_S = 48 * 3600.0`）。
- 控制面 list/steer/stop：`tools/delegate_tool_registry.py:198`（`_CONTROL_ACTIONS = frozenset({"list", "steer", "stop"})`）；steer 语义 `:124-135`（"AIAgent.steer() appends the text to the child's last tool result at its next iteration boundary — the current tool call is never cut … the text lands in the entry as ``missed_steer``"）；stop `:92-105` `interrupt_subagent`（"cooperative … recurses into grandchildren via AIAgent.interrupt()"）；所有权校验 `:213-235` `_owns_subagent_record`（weakref 血缘 + durable session lineage 双层）；结果条目 `:264-291` `_handle_control_action` + `:294-309` `_CONTROL_OUTCOMES`（stop:"Its partial result still re-enters the conversation as a completion message"）。
- 迭代预算：`tools/delegate_tool.py:71`（`DEFAULT_MAX_ITERATIONS = 250`）+ `:484-488`（"Caller-supplied max_iterations is ignored: the config value is authoritative"）。
- 全局暂停开关（运维级 stop）：`tools/delegate_tool_registry.py:39-48` `set_spawn_paused`/`is_spawn_paused`（"Globally block/unblock NEW delegate_task spawns (active children keep running)"）。

---

## 关键源码文件清单

| 文件（绝对路径） | 职责 |
|---|---|
| `/Users/apple/.hermes/hermes-agent/tools/delegate_tool.py` | 总入口 `delegate_task()`、`_build_child_agent`（子 AIAgent 构造）、`_run_single_child`、`DELEGATE_TASK_SCHEMA`、registry 注册、深度/预算闸门 |
| `/Users/apple/.hermes/hermes-agent/tools/delegate_tool_tasks.py` | 输入校验：tasks 归一化、goal 质量门、per-task output_schema / images（≤8） |
| `/Users/apple/.hermes/hermes-agent/tools/delegate_tool_toolsets.py` | 子工具集解析：继承父集、`DELEGATE_BLOCKED_TOOLS` 禁用名单、`delegation`/`kanban` 剔除、orchestrator 回补 `delegation` |
| `/Users/apple/.hermes/hermes-agent/tools/delegate_tool_progress.py` | 子系统提示词构造 `_build_child_system_prompt`、进度事件中继 `_ChildProgressRelay`、失败文案 |
| `/Users/apple/.hermes/hermes-agent/tools/delegate_tool_child_run.py` | 单个子运行 `_ChildRun`：workspace 播种/worktree、`await_child`（daemon worker、超时/陈旧处理）、schema 校验重试、结果 entry 组装 |
| `/Users/apple/.hermes/hermes-agent/tools/delegate_tool_dispatch.py` | 批执行 `_Batch`/`_run_children_parallel`、后台派发 `_dispatch_background`、同步回退 note、dispatch handle payload |
| `/Users/apple/.hermes/hermes-agent/tools/delegate_tool_results.py` | 摘要预算/裁剪/spill、tool 参数脱敏摘要、memory 通知、`subagent_stop` hook、成本 rollup |
| `/Users/apple/.hermes/hermes-agent/tools/delegate_tool_config.py` | `delegation.*` 配置旋钮（max_concurrent_children=10、max_spawn_depth=1、child_timeout、oneshot_max_children、orchestrator_enabled、worktree_isolation）与凭证路由 |
| `/Users/apple/.hermes/hermes-agent/tools/delegate_tool_registry.py` | 活跃子注册表 + 控制面 `list/steer/stop`、steer 线性化/missed_steer、spawn pause |
| `/Users/apple/.hermes/hermes-agent/tools/async_delegation.py` | 后台（异步）委派注册表：daemon executor、容量拒绝、`type="async_delegation"` 完成事件 → completion_queue、state.db 持久账本、陈旧监控 |
| `/Users/apple/.hermes/hermes-agent/tools/delegation_output_schema.py` | OUTPUT CONTRACT 注入、jsonschema 校验、一次有界重试 |
| `/Users/apple/.hermes/hermes-agent/tools/delegation_live_log.py` | 每任务实时 transcript（`cache/delegation/live/<id>/task-<n>.log`）与 manifest |
| `/Users/apple/.hermes/hermes-agent/agent/delegation_context.py` | 子执行上下文隔离：ContextVar 标记、Kanban worker 身份擦除/写围栏、子进程 env 传递 |
| `/Users/apple/.hermes/hermes-agent/agent/subagent_lifecycle.py` | 插件安全的子代理生命周期公共 API（`SubagentLaunchRequest/Handle/Result`，内部走 `_run_child_lifecycle`） |
| `/Users/apple/.hermes/hermes-agent/run_agent.py` | `AIAgent._dispatch_delegate_task`（模型工具调用唯一派发点，顶层强制后台/子内强制同步） |
| `/Users/apple/.hermes/hermes-agent/agent/review_engine.py` | `/review` 内部调用 `delegate_task` 的非模型入口 |
| `/Users/apple/.hermes/hermes-agent/toolsets.py` | toolset 定义：`"delegation": _ts("Spawn subagents with isolated context for complex subtasks", ["delegate_task"])`（:146） |
| `/Users/apple/.hermes/hermes-agent/tui_gateway/methods_subagents.py` | TUI/RPC 侧 `subagent.list/steer/stop`（与进程内注册表同源） |
| `/Users/apple/.hermes/hermes-agent/cron/scheduler.py` | cron 场景把 delegate_task 收敛为同步内联（stateless channel，:2259-2268） |
