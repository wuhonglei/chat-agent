# OpenAI Codex (codex-rs) 多 agent / 子 agent 实现方案分析

> 分析对象：`/Users/apple/Desktop/code/codex`（Rust workspace 位于 `codex-rs/`）。
> 结论先行：Codex **有真正的子 agent 机制**，即「协作多 agent（multi-agent）」体系——模型通过 `spawn_agent` 等协作工具派生独立的子 Codex 线程（thread/session），子 agent 是**完整的 agent 会话**（自己的消息循环、工具、模型调用），通过「agent 邮箱 + agent 间消息（InterAgentCommunication）」与父通信。此外还有三类**内部派生子 agent**（review、guardian/auto_review、memory consolidation、compact），复用同一套 `run_codex_thread_*` 基础设施但关闭协作能力。

整体架构分两条派生路径：

1. **协作子 agent（Multi-Agent V1 / V2）**：模型显式调用 `spawn_agent` 工具 → `LocalAgentControl::spawn_agent_internal` 创建子线程 → 父子以消息通信。V1 工具集在 `core/src/tools/handlers/multi_agents/`，V2 在 `core/src/tools/handlers/multi_agents_v2/`，工具 schema/描述集中在 `core/src/tools/handlers/multi_agents_spec.rs`。
2. **内部一次性子 agent（delegate）**：`core/src/codex_delegate.rs` 的 `run_codex_thread_one_shot` / `run_codex_thread_interactive`，被 review 任务、guardian 审批 reviewer、memory 合并等内部流程使用，`SubAgentSource` 标记来源（`Review` / `Compact` / `MemoryConsolidation` / `Other("guardian")` / `ThreadSpawn`）。

---

## 1. 创建子 agent 的时机

**结论**：协作子 agent 由**模型的工具调用显式触发**，入口工具名为 `spawn_agent`（V1 注册在 `multi_agent_v1` 命名空间，V2 注册在 `collaboration` 命名空间）；没有隐式任务拆分或中央调度器。是否允许派生由 feature 开关（`multi_agent_v2` / `Collab`）、模型能力、以及提示词中的 MultiAgentMode 门控（默认 `ExplicitRequestOnly`——只有用户明确要求并行/委派时才允许；推理档位为 `Ultra` 时切换为 `Proactive` 鼓励并行派生）。另有 4 类**内部隐式派生**（不经过工具调用）：代码评审（review）、审批 guardian（`approvals_reviewer = auto_review`）、记忆合并（memory consolidation）、压缩（compact）。核心入口函数：工具侧 `handle_spawn_agent` → `LocalAgentControl::spawn_agent_with_communication` / `spawn_agent_with_metadata` → `spawn_agent_internal`；内部派生侧 `run_codex_thread_one_shot` / `run_codex_thread_interactive`。

**证据**：

- `codex-rs/core/src/tools/handlers/multi_agents_v2/spawn.rs:43-46`（V2 工具名）：
  ```rust
  impl ToolExecutor<ToolInvocation> for Handler {
      fn tool_name(&self) -> ToolName {
          ToolName::plain("spawn_agent")
      }
  ```
- `codex-rs/core/src/tools/handlers/multi_agents_spec.rs:84-85`（V1 工具注册为命名空间工具）：
  ```rust
  tools: vec![ResponsesApiNamespaceTool::Function(ResponsesApiTool {
      name: "spawn_agent".to_string(),
  ```
  以及 `multi_agents_spec.rs:14-15`：
  ```rust
  pub const MULTI_AGENT_V1_NAMESPACE: &str = "multi_agent_v1";
  const MULTI_AGENT_V1_NAMESPACE_DESCRIPTION: &str = "Tools for spawning and managing sub-agents.";
  ```
- V2 命名空间常量：`codex-rs/core/src/config/mod.rs:256`：
  ```rust
  const DEFAULT_MULTI_AGENT_V2_TOOL_NAMESPACE: &str = "collaboration";
  ```
- 触发链（工具 → 控制器）：`codex-rs/core/src/tools/handlers/multi_agents_v2/spawn.rs:105-106`、`198-218`：
  ```rust
  async fn handle_spawn_agent(invocation: ToolInvocation) -> ...
      let spawned_agent = Box::pin(
          session.services.agent_control
              .spawn_agent_with_communication(config, communication, context, Some(spawn_source), ...)
  ```
  控制器入口：`codex-rs/core/src/agent/control/spawn.rs:287-302`（`spawn_agent_with_communication`）与 `632-638`（`spawn_agent_internal`）。
- 门控（工具是否暴露）：`codex-rs/core/src/tools/spec_plan.rs:643-655`：
  ```rust
  fn collab_tools_enabled(turn_context: &TurnContext, model_info: &ModelInfo) -> bool {
      match turn_context.multi_agent_version {
          MultiAgentVersion::Disabled => false,
          MultiAgentVersion::V1 => !exceeds_thread_spawn_depth_limit(...),
          MultiAgentVersion::V2 => { turn_context.session_source.get_agent_path().is_none()
              || model_info.multi_agent_version == Some(MultiAgentVersion::V2) }
      }
  }
  ```
  模型后端支持检查：`codex-rs/core/src/agent/child_config.rs:22-28`（`model_supports_multi_agent_backend`）。
- 时机提示（何时该派生）由 MultiAgentMode 文本控制：`codex-rs/core/src/session/multi_agents.rs:92-108`：
  ```rust
  if settings.effective_reasoning_effort() == Some(ReasoningEffort::Ultra) {
      (multi_agent_messages.proactive, MultiAgentMode::Proactive)
  } else {
      (multi_agent_messages.explicit, MultiAgentMode::ExplicitRequestOnly)
  }
  ```
- V1 工具描述中内置「何时委派」规则（提示词的一部分）：`codex-rs/core/src/tools/handlers/multi_agents_spec.rs:706-707`：
  ```
  Do not spawn sub-agents unless the user or applicable AGENTS.md/skill instructions explicitly ask for sub-agents, delegation, or parallel agent work.
  Requests for depth, thoroughness, research, investigation, or detailed codebase analysis do not count as permission to spawn.
  ```
- 内部隐式派生（非工具触发）：
  - review：`codex-rs/core/src/tasks/review.rs:128-136`（`run_codex_thread_one_shot(..., SubAgentSource::Review, ...)`）。
  - guardian 审批 reviewer（`approvals_reviewer=auto_review`，旧名 `guardian_subagent`）：`codex-rs/app-server-protocol/src/protocol/v2/shared.rs:243-248`：
    ```rust
    /// prompted subagent to gather relevant context and apply a risk-based
    #[serde(rename = "auto_review", alias = "guardian_subagent")]
    ```
    启动位置 `codex-rs/core/src/guardian/review_session_setup.rs:150-154`（`SubAgentSource::Other(GUARDIAN_REVIEWER_NAME)`）。
  - memory consolidation：`codex-rs/memories/README.md:111`（"spawns an internal consolidation sub-agent"）。
  - compact：`SubAgentSource::Compact`（见 `codex-rs/cli/src/doctor/thread_inventory.rs:677-683` 枚举来源：`Review`/`Compact`/`ThreadSpawn`/`MemoryConsolidation`/`Other`）。
- 另有一个 hook 身份名沿用 `spawn_agent`（兼容 Claude Code 风格 `Agent` hook 名）：`codex-rs/core/src/tools/hook_names.rs:43-48`：
  ```rust
  /// The serialized name remains `spawn_agent`, while `Agent` is accepted as
  /// ... sub-agent creation using Claude Code-style names.
  pub(crate) fn spawn_agent() -> Self { ... name: "spawn_agent".to_string(), ...
  ```

---

## 2. 子 agent 的上下文管理

**结论**：子 agent 是独立 thread，但**配置与指令继承父级**（base instructions（含 AGENTS.md 合成）、developer instructions、cwd、审批策略、沙箱/权限快照、exec policy、MCP/skills/plugins 服务），**对话历史是否继承由 `fork_turns` 参数控制**：`all`（默认）= 全历史 fork（复制父 rollout 并清洗），正整数 N = 只带最近 N 个 turn，`none` = 全新会话只带初始任务消息。fork 时会**主动剥离父级的多 agent 提示片段和父级 developer-instruction 片段**并为子级重建，避免父子提示互相污染。结果回传**原样**（子的最终 assistant 消息 `last_agent_message` 原文作为 `FINAL_ANSWER` 消息注入父历史），仅错误文本会截断到约 900 token；另有状态通知（V1 注入 `<subagent_notification>` JSON 片段，V2 发 `SubAgentActivity` 事件）。记忆（memories）管线对子 agent 会话禁用。

**证据**：

- 配置/指令继承：`codex-rs/core/src/agent/child_config.rs:102-120`：
  ```rust
  /// The returned config starts from the parent's effective config and then refreshes the
  /// model selection and reasoning settings captured for the invoking step, plus the turn's
  /// runtime approval policy, sandbox, and cwd.
      config.base_instructions = Some(base_instructions.text.clone());   // line 118
  ```
  运行时策略/cwd/权限快照继承：`child_config.rs:171-193`（`apply_spawn_agent_runtime_overrides`：`approval_policy`、`config.cwd = turn_cwd`、`set_permission_profile_from_session_snapshot`）。
- 内部 delegate 路径同样继承指令并可选 fork 历史：`codex-rs/core/src/codex_delegate.rs:74-77`：
  ```rust
  let conversation_history = initial_history.unwrap_or(InitialHistory::New);
  let instructions = parent_session.inherited_instructions().await;
  ```
  以及 `codex_delegate.rs:99-102,121-122`（子会话共享父的 `skills_service`、`plugins_manager`、`mcp_manager`、`inherited_exec_policy`）。
- fork_turns 语义：`codex-rs/core/src/tools/handlers/multi_agents_v2/spawn.rs:290-315`：
  ```rust
  let fork_turns = ... .unwrap_or("all");
  if fork_turns.eq_ignore_ascii_case("none") { return Ok(None); }
  if fork_turns.eq_ignore_ascii_case("all") { return Ok(Some(SpawnAgentForkMode::FullHistory)); }
  let last_n_turns = fork_turns.parse::<usize>()...
  ```
  Fork 模式类型：`codex-rs/core/src/agent/types.rs:21-25`（`FullHistory` / `LastNTurns(usize)`）。
- 全历史 fork 的复制与截断：`codex-rs/core/src/agent/control/spawn.rs:909-930`（`load_agent_model_context(...)` 复制父 rollout，`truncate_rollout_to_last_n_fork_turns(...)`）。
- fork 时的上下文隔离/清洗：`codex-rs/core/src/agent/control/spawn.rs:931-946`（收集父级 root/subagent usage hint 文本用于过滤）、`963-996`（`retain_forked_item` 过滤器：剥离父级 usage hint、替换 developer 指令片段、丢弃 `ResponseItem::AgentMessage`）、注释 `964-966`：
  ```rust
  // Scrub inherited hints and replace only the parent's developer-instruction fragment.
  ```
  fork 出的子会话持久化为副本：`codex-rs/core/src/codex_delegate.rs:107`（`fork_persistence: ForkPersistence::Copied`）。
- 结果回传（原样）：`codex-rs/core/src/agent/status.rs:9-12`：
  ```rust
  EventMsg::TurnComplete(ev) => Some(match &ev.error {
      Some(error) => AgentStatus::Errored(error.message.clone()),
      None => AgentStatus::Completed(ev.last_agent_message.clone()),
  ```
  渲染进父历史：`codex-rs/core/src/session_prefix.rs:24-35`：
  ```rust
  AgentStatus::Completed(Some(message)) => message.clone(),      // 最终消息原样
  AgentStatus::Errored(error) => {
      let error = truncate_text(error, TruncationPolicy::Tokens(ERROR_MAX_TOKENS));  // 仅错误截断
      format!("Agent errored: {error}\n\n{ERROR_NEXT_ACTION}")
  ```
  （`ERROR_MAX_TOKENS = COMPLETION_MESSAGE_MAX_TOKENS - 100` ≈ 900 token，`session_prefix.rs:9-12`。）
  消息格式：`codex-rs/core/src/context/inter_agent_completion_message.rs:40-45`：
  ```rust
  "Message Type: FINAL_ANSWER\nTask name: {}\nSender: {}\nPayload:\n{}"
  ```
- 状态通知（V1）：`codex-rs/core/src/agent/control.rs:677-682`（`inject_fragment_without_turn(SubagentNotification::new(...))`）；片段定义 `codex-rs/core/src/context/subagent_notification.rs:34-46`（`<subagent_notification>` 包裹 `{"agent_path": ..., "status": ...}` JSON）。V2 完成事件：`codex-rs/core/src/agent/control/completion.rs:68-85`（`SubAgentActivityItem { kind: SubAgentActivityKind::Completed, ... }`）。
- 记忆对子 agent 隔离：`codex-rs/memories/README.md:33-35`（触发条件含 "the session is not a sub-agent session"）。

---

## 3. 子 agent 的输入输出内容

**结论**：`spawn_agent` 输入是函数调用 JSON 参数：必填 `message`（任务描述，V2 支持加密标注）+ 必填 `task_name`（V2，规范任务名，组成 `/root/...` 路径），可选 `agent_type`（角色）、`model` / `reasoning_effort`（覆盖，受限制）、`fork_turns`（V2）或 `fork_context`（V1 布尔）；V1 还支持 `items` 结构化输入（text/image_url/audio_url/path/name，可传附件与 mention）。message 被包装为 agent 间消息（`Message Type: NEW_TASK\nTask name: ...\nSender: ...\nPayload:\n...`）作为子的首条输入。输出：`spawn_agent` 返回结构化结果（V2 `{"task_name", "nickname"}`，默认隐藏元数据时仅 `task_name`；V1 `{"agent_id", "nickname"}`）；**任务结果本体**是子 agent 的最终回答，以 `FINAL_ANSWER` 文本消息原样回传父级；`wait_agent` V2 返回 `{"message", "timed_out"}`，V1 返回状态联合类型（`{completed: string|null}` 可含最终消息）。

**证据**：

- V2 输入参数定义：`codex-rs/core/src/tools/handlers/multi_agents_spec.rs:630-666`：
  ```rust
  "message" => "Initial plain-text task for the new agent.".with_encrypted(),
  "agent_type" => "Agent type override for the new agent. Omit unless explicitly asked. ...",
  "fork_turns" => "Optional number of turns to fork. Defaults to `all`. Use `none`, `all`, or a positive integer string such as `3` ...",
  "model" / "reasoning_effort" => 覆盖说明
  ```
  必填项：`multi_agents_spec.rs:136-140`（`required: ["task_name", "message"]`；`task_name` 定义在 `118-124`："Task name for the new agent. Use lowercase letters, digits, and underscores."）。
  解析结构：`codex-rs/core/src/tools/handlers/multi_agents_v2/spawn.rs:270-280`：
  ```rust
  struct SpawnAgentArgs {
      message: String,
      task_name: String,
      agent_type: Option<String>,
      model: Option<String>,
      reasoning_effort: Option<ReasoningEffort>,
      fork_turns: Option<String>,
      fork_context: Option<bool>,     // V2 明确拒绝，见 283-288
  }
  ```
- V1 输入（含结构化附件）：`codex-rs/core/src/tools/handlers/multi_agents_spec.rs:591-628`（`message`/`items`/`agent_type`/`fork_context`/`model`/`reasoning_effort`）；items 字段 `560-583`（`text`、`image_url`、`audio_url`、`path`、`name`）。
- 任务消息在父子间的线格式：`codex-rs/core/src/context/inter_agent_message.rs:62-70`：
  ```rust
  format!("Message Type: {}\nTask name: {}\nSender: {}\nPayload:\n{}", ...)
  ```
  （类型为 `NEW_TASK` 或 `MESSAGE`，`inter_agent_message.rs:12-18`；由 `delivery.rs:37-50` 依据 `MessageDeliveryMode` 选择：`TriggerTurn → NewTask`、`QueueOnly → Message`。）
- `spawn_agent` 输出 schema（V2）：`codex-rs/core/src/tools/handlers/multi_agents_spec.rs:414-439`：
  ```rust
  "task_name": { "type": "string", "description": "Canonical task name for the spawned agent." },
  "nickname":  { "type": ["string","null"], ... }
  ```
  实际返回：`codex-rs/core/src/tools/handlers/multi_agents_v2/spawn.rs:252-260, 319-329`（`SpawnAgentResult::{WithNickname{task_name,nickname}, HiddenMetadata{task_name}}`；`hide_spawn_agent_metadata` 默认 `true`，见 `core/src/config/mod.rs:1332`）。V1 输出 `396-412`（`agent_id` + `nickname`）。
- 任务结果回传：见第 2 节 FINAL_ANSWER 格式（`inter_agent_completion_message.rs:40-45`，payload = 子的最终消息原文）。
- `wait_agent` 输出：V2 `codex-rs/core/src/tools/handlers/multi_agents_v2/wait.rs:132-160`（`WaitAgentResult { message, timed_out }`，message 为 "Wait completed." / "Wait interrupted by new input." / "Wait timed out."）；V1 状态 schema `multi_agents_spec.rs:365-394`（`{ "completed": string|null } | { "errored": string } | "pending_init|running|interrupted|shutdown|not_found"`），描述 `274`："Completed statuses may include the agent's final message."

---

## 4. 子 agent 的系统提示词

**结论**：协作子 agent **没有独立的"系统提示词文件"**——它继承父级 base instructions（模型指令 + AGENTS.md 等），其专属提示是一段 **developer 角色的 usage hint**，默认文本硬编码在 `codex-rs/prompts/src/model_messages/multi_agent.rs`（`DEFAULT_MULTI_AGENT_V2_SUBAGENT_USAGE_HINT_TEXT`，root 对应 `..._ROOT_AGENT_USAGE_HINT_TEXT`），由 `prompts/src/multi_agent_instructions.rs` 组合并包裹 `<multi_agent_role>` 标记注入。文本可被模型目录（`models-manager/models.json` 的 `multi_agent.role.subagent`）或配置项 `subagent_usage_hint_text` / `subagent_developer_instructions` 覆盖。内部子 agent 则整体**替换**系统提示：review 子 agent 用 `prompts/templates/review/rubric.md`（`REVIEW_PROMPT`），guardian reviewer 用 `prompts/templates/guardian/policy.md`（风险决策策略）。

**证据**：

- 子 agent 默认提示词全文（关键片段）：`codex-rs/prompts/src/model_messages/multi_agent.rs:27-45`：
  ```
  You are an agent in a team of agents collaborating to complete a task.

  You can spawn sub-agents to handle subtasks, and those sub-agents can spawn their own sub-agents. All agents in the team, ... are equally intelligent and capable, and have access to the same set of tools.

  You can use `spawn_agent` to create a new agent, `followup_task` to give an existing agent a new task and trigger a turn, and `send_message` to pass a message to a running agent.
  ...
  When you provide a response in the final channel, that content is immediately delivered back to your parent agent.

  You will receive messages in the analysis channel in the form:
  Message Type: NEW_TASK | MESSAGE | FINAL_ANSWER
  Task name: <recipient>
  Sender: <author>
  Payload:
  <payload text>
  ```
  root 提示（`7-26`）开头：`"You are \`/root\`, the primary agent in a team of agents collaborating to fulfill the user's goals."`。模式文本（`46-47`）：`EXPLICIT_REQUEST_ONLY_MULTI_AGENT_MODE_TEXT`（"Do not spawn sub-agents unless the user ... explicitly ask"）与 `PROACTIVE_MULTI_AGENT_MODE_TEXT`（"Proactive multi-agent delegation is active. ... If at any point you can parallelize work by delegating tasks to another agent ... you should do so"）。
- 组合与包装：`codex-rs/prompts/src/multi_agent_instructions.rs:55-56, 59-91`（`type_markers() -> ("<multi_agent_role>", "</multi_agent_role>")`；`body()` 拼接 base + 共享提示 + 并发槽数）；共享提示 `11-17`（"All agents share the same directory ... edits made by one agent are immediately visible to all other agents."；并注明协作工具不能在 `functions.exec` 内调用）；并发提示行 `81-83`（`"There are {max_concurrency} available concurrency slots, meaning that up to {max_concurrency} agents can be active at once, including you."`）。注入为 developer 消息：`multi_agent_instructions.rs:40-46`（`role() -> "developer"`，`requires_separate_message() -> true`）。
- 选择/覆盖链：`codex-rs/core/src/session/multi_agents.rs:39-75`（`resolve_usage_hints`：配置 `subagent_usage_hint_text` 优先，其次模型目录文本，再次 bundled 默认；子 agent 会话取 `snapshot.subagent`，见 `27-36`）；模型目录覆盖示例 `codex-rs/models-manager/models.json:98-99`（`"root"` / `"subagent"` 键）；配置字段 `codex-rs/core/src/config/mod.rs:1307-1310`（`usage_hint_text` / `root_agent_usage_hint_text` / `subagent_usage_hint_text` / `subagent_developer_instructions`）。`subagent_developer_instructions` 直接替换子的 developer instructions：`codex-rs/core/src/agent/child_config.rs:145-153`。
- V1 spawn 工具描述本身承载大量行为指引（何时委派/如何拆任务/并行模式）：`codex-rs/core/src/tools/handlers/multi_agents_spec.rs:701-737`（"### When to delegate vs. do the subtask yourself"、"### Designing delegated subtasks"、"### After you delegate"、"### Parallel delegation patterns"）。V2 工具描述 `761-768`（"The spawned agent will have the same tools as you and the ability to spawn its own subagents. ... its final answer will be provided to you when it finishes."）。
- review 子 agent 系统提示：`codex-rs/prompts/src/review_request.rs:8-9`：
  ```rust
  /// Review thread system prompt.
  pub const REVIEW_PROMPT: &str = include_str!("../templates/review/rubric.md");
  ```
  模板开头 `prompts/templates/review/rubric.md:1-3`（"# Review guidelines: / You are acting as a reviewer for a proposed code change made by another engineer."）。
- guardian reviewer 策略提示：`codex-rs/core/src/guardian/prompt.rs:55`（"The fixed guardian policy lives in the review session developer message."）；模板 `codex-rs/prompts/templates/guardian/policy.md:1-4`（"## Environment Profile ... ## Risk Taxonomy and Allow/Deny Rules / ### Data Exfiltration ..."），占位符机制见 `prompts/src/guardian_instructions.rs:8-17`（`{{ tenant_policy_config }}`、`{{ extra_policy }}`、`policy_template`）。

---

## 5. 子 agent 的工具范围

**结论**：协作子 agent **继承父级的全部工具与服务**（同一套 MCP/skills/plugins/沙箱；提示词明确 "The spawned agent will have the same tools as you"），没有白名单裁剪；但有以下差异/限制：(a) **深度限制**：V1 由 `agent_max_depth`（默认 1）控制——超限时 `spawn_agent` 工具直接从工具集中移除且调用被拒（"Agent depth limit reached. Solve the task yourself."）；V2 提示词明确允许子再生子（任务名组成 `/root/...` 路径树），V2 的 spawn 处理器中**没有深度检查**，靠并发/线程总数上限约束。(b) **内部 delegate 完全禁止再派生**：review/guardian/compact/记忆合并子 agent 把 multi-agent 版本置为 `Disabled` 或禁用 `Collab`/`MultiAgentV2` feature（防递归委派）。(c) **执行并发限制只作用于 V2 子 agent**（root 与 V1 不受限）。(d) 角色（`agent_type`）可叠加一层 TOML 配置覆盖（developer_instructions/model/reasoning_effort 及任意 config 层）。(e) 协作工具不能在 `functions.exec` 代码模式内调用。

**证据**：

- 同套工具的表述：`codex-rs/core/src/tools/handlers/multi_agents_spec.rs:763`（"The spawned agent will have the same tools as you and the ability to spawn its own subagents."）；`prompts/src/model_messages/multi_agent.rs:11`（"All agents in the team ... have access to the same set of tools."）。
- 服务/策略继承（工具运行时同源）：`codex-rs/core/src/codex_delegate.rs:99-102,121-122`（子会话拿父的 `skills_service`、`plugins_manager`、`mcp_manager`、`inherited_exec_policy`）。
- V1 深度限制（默认 1 层）：`codex-rs/core/src/config/mod.rs:261`（`pub(crate) const DEFAULT_AGENT_MAX_DEPTH: i32 = 1;`）；深度计算 `codex-rs/core/src/agent/registry.rs:80-86`（`next_thread_spawn_depth` / `exceeds_thread_spawn_depth_limit`）；超限拒绝 `codex-rs/core/src/tools/handlers/multi_agents/spawn.rs:71-77`：
  ```rust
  if exceeds_thread_spawn_depth_limit(child_depth, max_depth) {
      return Err(FunctionCallError::RespondToModel(
          "Agent depth limit reached. Solve the task yourself.".to_string()));
  ```
  工具随深度隐藏：`codex-rs/core/src/tools/spec_plan.rs:646-649`（V1 下 `!exceeds_thread_spawn_depth_limit(...)` 才暴露 collab 工具）。
- V2 允许子再生子、且 spawn 无深度检查：提示词 `prompts/src/model_messages/multi_agent.rs:29-32`（"You can spawn sub-agents ... and those sub-agents can spawn their own sub-agents."）；`multi_agents_v2/spawn.rs` 全文无 `exceeds_thread_spawn_depth_limit`/`agent_max_depth` 引用（仅 `multi_agents/spawn.rs`、`multi_agents/resume_agent.rs`、`spec_plan.rs` 使用）。任务树用 `AgentPath` 命名：`codex-rs/protocol/src/agent_path.rs:54-57`（`join` 生成 `/root/task1/task_3` 式路径）。
- 内部 delegate 禁止递归：
  - `codex-rs/core/src/codex_delegate.rs:134`（`inherited_multi_agent_version: Some(MultiAgentVersion::Disabled)`）；
  - review：`codex-rs/core/src/tasks/review.rs:107-116`：
    ```rust
    // Carry over review-only feature restrictions so the delegate cannot
    // re-enable blocked tools (web search, collab tools, view image).
    ... WebSearchMode::Disabled ...
    let _ = sub_agent_config.features.disable(Feature::Collab);
    let _ = sub_agent_config.features.disable(Feature::MultiAgentV2);
    ```
  - 记忆合并：`codex-rs/memories/README.md:114-115`（"runs it with no approvals, no network, and local write access only / disables collab for that agent (to prevent recursive delegation)"）。
- 并发限制仅 V2 子 agent：`codex-rs/core/src/agent/control/execution.rs:95-101`：
  ```rust
  fn is_execution_limited(...) -> bool {
      multi_agent_version == MultiAgentVersion::V2
          && matches!(session_source, SessionSource::SubAgent(_))
  }
  ```
  模块注释 `execution.rs:2`（"root and MAv1 turns remain unrestricted."）。
- 审批/沙箱差异：协作子 agent 与父共享同一审批策略与权限快照（`child_config.rs:175-192`）；而内部 delegate 强制 `approval_policy = never`（`codex-rs/core/src/codex_delegate.rs:63-68`："Codex delegates require approval policy `never`"；review 同样 `tasks/review.rs:121`）。
- 角色覆盖范围：`codex-rs/core/src/agent/role.rs:36-39, 50-52`（`AgentRoleOverrides { developer_instructions, model, model_reasoning_effort }` + `apply_role_to_config` 叠加角色 TOML 配置层，`role.rs:79-83`）；角色元数据 `codex-rs/agent-roles/src/agent_role_config.rs:10-18`（`description` / `config_file` / `nickname_candidates`）。
- `functions.exec` 限制：`codex-rs/prompts/src/multi_agent_instructions.rs:11-12`（"Note that collaboration tools cannot be called from inside `functions.exec` ... since they are intentionally absent from the `functions.exec` `tools.*` namespace."）。

---

## 6. 子 agent 的运行方式

**结论**：`spawn_agent` **异步非阻塞**——工具调用只创建子线程并投递首条任务消息，随即返回 `task_name`，子 agent 在自己的会话循环里后台并发运行；父通过 `wait_agent`（唯一阻塞同步点）或被动收取邮箱消息感知结果。并发上限：V2 默认 **4 个并发执行槽（含 root 自己）**（`max_concurrent_threads_per_session`），root 的 V1 每用户会话总共默认 **6 个子线程**（`agent_max_threads`，超限报 `AgentLimitReached`）；V2 另有 residency 机制可逐出空闲子 agent 并支持恢复。超时：没有全局子 agent 运行超时，只有 `wait_agent` 的等待超时（默认 30s，最小 10s，最大小硬顶 1h；V1 对越界值 clamp，V2 超最大值报错）。结果通知回父：子线程终态自动路由——把 `FINAL_ANSWER` 消息以 `trigger_turn=false` 投进父邮箱（不打断父的 turn，父在下一条活动时读到），V1 另注入 `<subagent_notification>`，V2 另发 `SubAgentActivity` 完成事件；`wait_agent` 被邮箱活动唤醒返回 "Wait completed."。

**证据**：

- 异步 spawn：`codex-rs/core/src/agent/control/spawn.rs:802-817`（创建线程后仅 `send_input` / `send_inter_agent_communication_after_capacity_check` 投递初始输入）→ `832-836`（立即 `Ok(LiveAgent { thread_id, metadata, status })` 返回）。子会话独立运行（每个 thread 一个 `Session`，`codex_delegate.rs:86` `Session::spawn(...)`）。
- 后台完成监听（V1）：`codex-rs/core/src/agent/control.rs:608`（`tokio::spawn(async move { ... 订阅子状态直到 final ... })`，函数注释 `590-593`："Starts a detached watcher for sub-agents spawned from another thread."）。
- `wait_agent` 阻塞语义：V2 `codex-rs/core/src/tools/handlers/multi_agents_v2/wait.rs:94-96`（`let deadline = Instant::now() + Duration::from_millis(timeout_ms)` → `wait_for_activity(...)`，阻塞到邮箱活动/steer/超时）；V1 `codex-rs/core/src/tools/handlers/multi_agents/wait.rs:120-130`（订阅各目标状态直到 `is_final`）。
- 超时常量：`codex-rs/core/src/config/mod.rs:253-255`：
  ```rust
  DEFAULT_MULTI_AGENT_V2_MIN_WAIT_TIMEOUT_MS: i64 = 10_000;
  DEFAULT_MULTI_AGENT_V2_MAX_WAIT_TIMEOUT_MS: i64 = 3600 * 1000;
  DEFAULT_MULTI_AGENT_V2_DEFAULT_WAIT_TIMEOUT_MS: i64 = 30_000;
  ```
  V1 clamp：`codex-rs/core/src/tools/handlers/multi_agents/wait.rs:92-100`（`clamp(MIN_WAIT_TIMEOUT_MS, MAX_WAIT_TIMEOUT_MS)`）；V2 超上限报错：`multi_agents_v2/wait.rs:57-65`（"timeout_ms must be at most {max_timeout_ms}"）。
- 并发上限：`codex-rs/core/src/config/mod.rs:251-252`（`DEFAULT_AGENT_MAX_THREADS: Option<usize> = Some(6); DEFAULT_MULTI_AGENT_V2_MAX_CONCURRENT_THREADS_PER_SESSION: usize = 4;`）；总线程配额 `codex-rs/core/src/agent/registry.rs:19-24, 89-101`（"limits: Total number of sub-agents (i.e. threads) per user session"；`reserve_spawn_slot` 超限返回 `CodexErrorDetails::AgentLimitReached { max_threads }`）；V2 并发槽在提示词中告知模型（`prompts/src/multi_agent_instructions.rs:81-83`，"up to {max_concurrency} agents can be active at once, including you"）；V2 residency 槽位：`spawn.rs:653-663`（`reserve_v2_residency_slot`）+ `core/src/agent/control/residency.rs`（空闲逐出与恢复）。
- 结果通知回父：`codex-rs/core/src/agent/control/completion.rs:25-37`（`notify_parent_of_terminal_turn`：只对 `SubAgentSource::ThreadSpawn` 生效）、`88-113`（把 `format_inter_agent_completion_message(...)` 作为 `InterAgentCommunication` 发给父线程，`103` 行 `/*trigger_turn*/ false`——不唤醒父）；V1 的 `<subagent_notification>` 注入 `control.rs:674-682`；V2 的 `SubAgentActivity` 事件 `completion.rs:68-85`。
- 消息投递模式：`codex-rs/core/src/agent/types.rs:55-61`（`QueueOnly`："Deliver to the mailbox without starting an idle agent." / `TriggerTurn`："Deliver to the active turn or start work if the agent is idle."）；`send_message` 描述 "Does not trigger a new turn."（`multi_agents_spec.rs:204`），`followup_task` 描述 "trigger a turn if it is idle"（`multi_agents_spec.rs:237`）。
- 阻塞到唤醒路径：`wait_agent` V2 监听 `InputQueueActivity::Mailbox/Steer`（`multi_agents_v2/wait.rs:180-201`），结果 `"Wait completed."`（`wait.rs:144-147`）。
- one-shot delegate 自动关停：`codex-rs/core/src/codex_delegate.rs:248-269`（事件桥在 `TurnComplete | TurnAborted` 后发送 `Op::Shutdown` 并 cancel——内部子 agent 跑完一轮即终止）。
- （附加）V2 子 agent 不接受外部直接输入：`codex-rs/app-server/src/request_processors/thread_input.rs:9`（"direct app-server input is not allowed for multi-agent v2 sub-agents"）。

---

## 关键源码文件清单

| 文件 | 作用 |
|---|---|
| `codex-rs/core/src/tools/handlers/multi_agents_spec.rs` | V1/V2 全部协作工具的 schema、描述、输出 schema（spawn_agent/send_input/send_message/followup_task/wait_agent/list_agents/close_agent/interrupt_agent/resume_agent） |
| `codex-rs/core/src/tools/handlers/multi_agents_v2/spawn.rs` | V2 `spawn_agent` 处理器（`handle_spawn_agent`、`SpawnAgentArgs`、`SpawnAgentResult`、fork_turns 解析） |
| `codex-rs/core/src/tools/handlers/multi_agents_v2/wait.rs` | V2 `wait_agent`（邮箱活动等待、超时 clamp/报错） |
| `codex-rs/core/src/tools/handlers/multi_agents_v2/{send_message,followup_task,interrupt_agent,list_agents,message_tool,analytics}.rs` | V2 其余协作工具 |
| `codex-rs/core/src/tools/handlers/multi_agents/{spawn,wait,send_input,close_agent,resume_agent}.rs` | V1 协作工具（含深度限制检查） |
| `codex-rs/core/src/tools/handlers/multi_agents_common.rs` | 协作工具公共逻辑（等待超时常量、`thread_spawn_source`、错误映射） |
| `codex-rs/core/src/tools/handlers/multi_agent_tool.rs` | Multi-Agent V2 目录覆盖（namespace/description/parameters override） |
| `codex-rs/core/src/tools/spec_plan.rs` | 工具面装配与门控（`collab_tools_enabled`、`required_child_management_tool_names`） |
| `codex-rs/core/src/agent/control/spawn.rs` | 子线程创建核心（`spawn_agent_internal`、fork 历史复制/清洗、residency） |
| `codex-rs/core/src/agent/control/completion.rs` | 子 agent 终态结果回传父（FINAL_ANSWER 消息路由） |
| `codex-rs/core/src/agent/control/delivery.rs` | agent 间消息投递（`MessageDeliveryMode` → NEW_TASK/MESSAGE） |
| `codex-rs/core/src/agent/control/execution.rs` | V2 子 agent 并发执行限制器 |
| `codex-rs/core/src/agent/control.rs` | V1 完成 watcher（`<subagent_notification>` 注入）、元数据/昵称分配 |
| `codex-rs/core/src/agent/registry.rs` | agent 注册表（总线程数限制 `AgentLimitReached`、深度计算） |
| `codex-rs/core/src/agent/child_config.rs` | 子 agent 配置合成（指令/模型/审批/cwd/权限继承与覆盖） |
| `codex-rs/core/src/agent/role.rs` + `codex-rs/agent-roles/src/agent_role_config.rs` | agent 角色（agent_type）配置 |
| `codex-rs/core/src/agent/types.rs` | `SpawnAgentOptions`/`SpawnAgentForkMode`/`MessageDeliveryMode`/`AgentMessage` |
| `codex-rs/core/src/codex_delegate.rs` | 内部子 Codex 派生（`run_codex_thread_interactive` / `run_codex_thread_one_shot`） |
| `codex-rs/core/src/session_prefix.rs` | FINAL_ANSWER 完成消息渲染与错误截断 |
| `codex-rs/core/src/context/{inter_agent_message,inter_agent_completion_message,subagent_notification}.rs` | agent 间消息/完成通知/状态通知的线格式 |
| `codex-rs/core/src/session/multi_agents.rs` | usage hint / MultiAgentMode 解析 |
| `codex-rs/prompts/src/model_messages/multi_agent.rs` | root/subagent 默认提示词、explicit/proactive 模式文本 |
| `codex-rs/prompts/src/multi_agent_instructions.rs` | `<multi_agent_role>` 组合（共享文件系统说明、并发槽、wait 指引） |
| `codex-rs/core/src/tasks/review.rs` + `codex-rs/prompts/templates/review/rubric.md` | review 内部子 agent 及其系统提示 |
| `codex-rs/core/src/guardian/{prompt,review_session,review_session_setup}.rs` + `codex-rs/prompts/templates/guardian/policy.md` | guardian（auto_review 审批）子 agent 及风险策略提示 |
| `codex-rs/memories/README.md` | 记忆合并内部子 agent（禁 collab 防递归） |
| `codex-rs/core/src/config/mod.rs` | 全部限额常量与 `MultiAgentV2Config` |
| `codex-rs/core/src/agent/status.rs` | 事件 → `AgentStatus`（`Completed(last_agent_message)`） |
| `codex-rs/protocol/src/agent_path.rs` | 任务路径树（`/root/task...`） |
