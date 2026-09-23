# ZCode 多 Agent / 子 Agent（Subagent）实现方案分析

> 分析对象：`/Users/apple/Desktop/code/ZCode`（monorepo，核心实现位于 `apps/zcode-cli/packages/`）。
> ZCode 有两条多 agent 路径：
> ① **Agent/Task 工具派生子 agent（Subagent）**——本文主线，一次性子运行时（general-purpose / Explore / 自定义 profile）；
> ② **Dynamic Workflow（CreateWorkflow）**——用户显式点名 workflow 时的脚本化多 agent 编排（TypeScript 脚本 + 引擎调度 actor），仅在相关关注点处补充说明。

---

## 1. 创建子 agent 的时机

**结论**：子 agent 只由**父模型的工具调用**触发，入口工具名是 `Agent`（另有 Claude Code 兼容别名 `Task`）；没有隐式任务拆分器或自动调度器。工具描述引导模型在「任务匹配某个 agent 类型 / 有可并行的独立工作 / 需要横扫多文件读取」时委派；`run_in_background: true` 或 profile `background: true` 走后台启动。另一条独立入口是 `SendMessage` 对已完成 agent 的续跑（重新以后台拉起同一 child session）。用户显式点名 workflow 时改走 `CreateWorkflow`（动态工作流引擎，脚本编排多个 subagent），且该情形禁止用 Agent 工具替代。调度式派生仅存在于动态工作流内部（脚本 actor），未找到「调度器自动派生 subagent」或隐式拆分的实现。

**证据**：
- `apps/zcode-cli/packages/core/src/tool/handlers/agent.ts:174-222`（入口 handler）：
  `const agentHandler: ToolHandler = async (input, context) => { ... return context.subagentPort.launch({ ...request, runInBackground: parsed.run_in_background === true }, ...) }`
- `apps/zcode-cli/packages/core/src/tool/handlers/agent.ts:224-228`：`metadata: { name: "Agent", ... }`，`:287-299` `taskToolEntry` 注册别名 `TASK_TOOL_NAME`。
- `apps/zcode-cli/packages/core/src/tool/compat.ts:1-4`：`const AGENT_TOOL_NAME = "Agent"; export const TASK_TOOL_NAME = "Task"; const subagentDispatchToolNames = new Set<string>([AGENT_TOOL_NAME, TASK_TOOL_NAME]);`
- 触发条件（工具描述）`agent.ts:109-116`：
  `"## When to use"` / `"Reach for this when the task matches an available agent type, when you have independent work to run in parallel, or when answering would mean reading across several files — delegate it and you keep the conclusion, not the file dumps."`；`:115` `"- \`run_in_background: true\` runs the agent asynchronously; you'll be notified when it completes."`
- workflow 优先规则 `agent.ts:123`：`'- If the user explicitly asks for a workflow (...), the CreateWorkflow tool is mandatory: do not use this tool instead, however small the task.'`
- 动态工作流入口 `apps/zcode-cli/packages/core/src/tool/handlers/create-workflow-description.ts:8`：`"Create and run a dynamic workflow: a TypeScript script ... that orchestrates multiple model-driven subagents with plain control flow (loops, conditionals, fan-out) ..."`；`:42`：`"Do not substitute the Agent/Task subagent tools ..."`
- 派生分叉（前台/后台）`apps/zcode-cli/packages/core/src/subagent/runner.ts:147-170`：`const backgroundRequested = rawRequest.runInBackground === true || profile.background === true; if (backgroundRequested) { ... return port.start(...) } return port.run(executionRequest, launchOptions);`
- SendMessage 续跑入口 `apps/zcode-cli/packages/core/src/tool/handlers/send-message.ts:69-82` → `runner.ts:955` `resumeTerminalAgentInBackground(...)`。
- **未找到**：自动/隐式拆分（不经模型 tool call 派生 subagent）的代码路径；`packages/dynamic-workflow/src/engine/scheduler.ts` 是工作流脚本 actor 的调度器，不派生 Agent 工具的 subagent。

---

## 2. 子 agent 的上下文管理

**结论**：子 agent 运行在**独立的新会话**（`childSessionId = subagent_<agentId>`）里，**不继承父对话历史**——输入只有 prompt 一条（prompt 必须自包含），工具描述明说 "A new Agent call starts fresh"。继承项：工作目录/workspaceRoot、envInfo（平台/shell/OS，取父快照）、AGENTS.md 用户指令（`injectAgentsMd` 时）、父的不可变 Model（未显式选模时）、父 MCP 启动快照（借连接，可按 `mcpServers` 收窄）、父 SkillPort（按 profile `skills` 过滤）；**不继承** Project Context 与父会话记忆。记忆是 profile 级的独立持久记忆（`memory: user|project|local` 作用域 + `MEMORY.md` 索引），非父子共享。结果回传是**子 agent 最后一条 assistant 文本原样**（无 LLM 摘要），外加 agentId/usage 附注；超 120KB 走 artifact + head 预览截断。隔离方面：child 事件按 childSessionId 落库，父 timeline 只收 `source: "subagent"` 的工具事件镜像，raw 正文不进父时间线。

**证据**：
- 独立子会话 `apps/zcode-cli/packages/core/src/subagent/runner.ts:806`：`const childSessionId = createSessionId(\`subagent_${agentId}\`);`
- 不继承历史 `apps/zcode-cli/packages/core/src/tool/handlers/agent.ts:114`：`"- A new Agent call starts fresh, so the prompt must be self-contained."`；child 只收 prompt：`apps/zcode-cli/packages/core/src/runtime/methods/subagent.ts:399-406`：`return await childRuntime.executeTurn(request.prompt, undefined, { abortSignal: ..., inputSource: "subagent", inputPresentation: "coordinator_input", ... });`
- 工作目录继承 `subagent.ts:251`：`workingDirectory: request.workingDirectory,`（请求字段来自 `agent.ts:200-202` `workingDirectory: context.workingDirectory, workspaceRoot: context.workspaceRoot`）；envInfo 继承父快照 `subagent.ts:113-126`（`const baseChildEnvInfo = this.contextSourceSnapshot?.envInfo ?? ...`）。
- AGENTS.md 指令继承 `subagent.ts:96-99`：`request.profile.injectAgentsMd !== false ? this.contextSourceSnapshot?.userInstructions : undefined`；`:266` `...(agentsMdInstructions ? { userInstructions: agentsMdInstructions } : {})`（`injectAgentsMd` 字段见 `profile.ts:26`）。
- Project Context 不继承 `subagent.ts:262`（注释）：`// child 只复用父 runtime 已解析的 instructions snapshot；Project Context 仍不继承。`
- 模型继承 `apps/zcode-cli/packages/contracts/src/interfaces/subagent.port.ts:26-27`：`/** 未显式选模的 child 从父 Agent Loop 继承的不可变 Model。 */ model?: Model;`；`subagent.ts:107`：`const inheritedModel = !modelOverride && !hasConcreteModel ? options?.model : undefined;`
- MCP 借用父快照 `subagent.ts:581`（注释）：`// child 不拥有连接生命周期，只能复用 parent constructor 已创建的启动快照。`；`subagent.ts:607-612` `createBorrowedSubagentMcpAccess(this.mcpPort, parentStartupSnapshot, scopedServerNames, ...)`。
- 独立持久记忆（非父记忆）`apps/zcode-cli/packages/core/src/subagent/persistent-memory.ts:24-30`（作用域目录：`agent-memory/<key>` / `.zcode/agent-memory/<key>` / `.zcode/agent-memory-local/<key>`）、`:94-100` 读取各自的 `MEMORY.md`；注入 prompt 模板 `persistent-memory-prompt.ts:150-168`。
- 结果回传（原样最终消息）`runner.ts:1176-1181`：`content: [{ type: "text", text: childResult.response }]`；父模型面格式化 `agent.ts:136-150`：`const childText = data.content.map((block) => block.text).join("\n"); ... agentId: ${data.agentId} (use SendMessage with to: ...)` + `<usage>tool_uses / duration_ms</usage>`——**无摘要改写**。
- 回传截断 `agent.ts:21`：`const MAX_AGENT_MODEL_BYTES = 120_000;`；`agent.ts:254-266` `resultBudget: { maxInlineBytes: 120_000, strategy: "artifact", preview: { maxBytes: 120_000, direction: "head" }, artifact: { enabled: true, retention: "session" } }`。
- 父子时间线隔离 `apps/zcode-cli/packages/core/src/subagent/tool-event-mirror.ts:19-25`（只镜像 ToolCall* 与 Permission* 事件）、`:92` `source: SUBAGENT_EVENT_SOURCE`（`:17` = `"subagent"`）；`subagent.ts:357-358`（注释）`// parent mirror 保留原语义：父会话只看到 subagent 摘要/工具活动，raw child 正文不会污染父 timeline。`；`apps/zcode-cli/packages/tui/SUBAGENTS.md:6`：`Main transcript admission rejects both foreign session IDs and parent-session tool mirrors (source: subagent).`

---

## 3. 子 agent 的输入输出内容

**结论**：输入 payload（模型面）是 4 字段的扁平 JSON：`description`（3-5 词短描述）、`prompt`（任务全文，唯一任务载体）、`subagent_type`（选 profile，缺省 `general-purpose`）、`run_in_background`（可选布尔）；**没有附件/文件字段**，文件靠 prompt 里的路径引用。运行时另有内部请求结构（sessionId、turnId、parentToolCallId、workingDirectory、workspaceRoot、trace）。输出两种结构化结果：同步完成 `AgentCompletedOutput`（status/agentId/agentType/description/prompt/content:[{type:"text",text}] 全文/totalToolUseCount/totalDurationMs/totalTokens?/usage?）和后台启动 `AgentBackgroundedOutput`（status:"async_launched" + outputFile + canReadOutputFile）。此外每个 agent 落盘 3 个文件：`metadata.json`、`output.txt`、`task.output`（同一文本），后台模式下 `outputFile` 供父方自查进度。

**证据**：
- 输入 schema `apps/zcode-cli/packages/contracts/src/tools/agent.ts:18-33`：
  `description: z.string().describe("A short (3-5 word) description of the task"), prompt: z.string().describe("The task for the agent to perform"), subagent_type: z.string().optional()..., run_in_background: z.boolean().optional().describe("Set to true to run this agent in the background. ...")`（`:25-26` 注释说明刻意不暴露 model 参数）。
- **未找到** attachments/文件上传类输入字段（prompt 为自由文本）。
- 内部运行请求 `apps/zcode-cli/packages/contracts/src/interfaces/subagent.port.ts:11-22`：`SubagentRunRequest { sessionId, turnId?, parentToolCallId, agentType, description, prompt, callerCanReadOutputFile?, workingDirectory, workspaceRoot, trace }`。
- 输出结构 `contracts/src/tools/agent.ts:44-70`：`AgentCompletedOutput { status: "completed", agentId, agentType, description, prompt, content: AgentTextContentBlock[], totalToolUseCount, totalDurationMs, totalTokens?, usage? }`；`AgentBackgroundedOutput { status: "async_launched", isAsync: true, agentId, ..., outputFile, canReadOutputFile }`。
- 输出文件 `runner.ts:808-815`：`agentOutputDir = join(outputRootDir ?? join(tmpdir(), "zcode-agents"), request.sessionId, agentId)`，其下 `metadata.json` / `output.txt` / `task.output`（`:813-815`）；写入 `runner.ts:1923-1937` `writeCompletedAgentArtifacts`（`output.txt`+`task.output` 全文、`metadata.json` 状态与 usage）；metadata 字段 `runner.ts:1997-2016`（agentId、childSessionId、parentSessionId、parentToolUseId、profileId、profileSnapshot、prompt、status、cwd、workspaceRoot ...）。
- `canReadOutputFile` 判定 `agent.ts:282-285`：`return names.has("Read") || names.has("Bash");`

---

## 4. 子 agent 的系统提示词

**结论**：系统提示是**代码内常量/模板拼装**，分 4 层：① profile 的 `systemPrompt`（内置 general-purpose / Explore 各有硬编码模板文件；自定义 profile 的系统提示 = markdown 正文，frontmatter 定义元数据）；② 公共 Notes（绝对路径、无 emoji、禁止写报告 md 等）；③ 环境块（cwd/git/platform/shell/OS/模型名）；④ 可选的持久记忆模板 + AGENTS.md 指令 + skills 列表（后两者进 meta user 附件）。Explore 用专门的只读提示（"READ-ONLY MODE"）。

**证据**：
- general-purpose 模板 `apps/zcode-cli/packages/core/src/subagent/general-purpose.ts:7-24` `buildGeneralPurposeSystemPrompt()`，核心片段（:9）：
  `"You are an agent for ZCode CLI. Given the user's message, you should use the tools available to complete the task. Complete the task fully—don't gold-plate, but don't leave it half-done. When you complete the task, respond with a concise report covering what was done and any key findings — the caller will relay this to the user, so it only needs the essentials."`（:22 `"NEVER proactively create documentation files (*.md) or README files."`）
- Explore 模板 `apps/zcode-cli/packages/core/src/subagent/explore.ts:20-68` `buildExploreAgentPrompt()`，核心片段（:35-38）：
  `"You are ZCode Explore, a file search and codebase research specialist ..."` / `"=== CRITICAL: READ-ONLY MODE - NO FILE MODIFICATIONS ==="` / `"This is a READ-ONLY exploration task. You are STRICTLY PROHIBITED from: - Creating new files ... - Using redirect operators (>, >>, |) ..."`（:60 `"Communicate your final report directly as a regular message - do NOT attempt to create files"`）
- 公共 Notes `apps/zcode-cli/packages/core/src/subagent/system-prompt.ts:10-19` `buildSubagentCommonNotes()`，关键行（:13、:17）：
  `"- Agent threads always have their cwd reset between bash calls, as a result please only use absolute file paths."`；`"- Do NOT Write report/summary/findings/analysis .md files. Return findings directly as your final assistant message — the parent agent reads your text output, not files you create."`
- 环境块 `system-prompt.ts:21-40`：`"Here is useful information about the environment you are running in:" <env> Working directory / Is directory a git repo / Platform / Shell / OS Version </env>` + `"You are powered by the model named ${model.providerId}/${model.modelId}."`
- 组装顺序 `apps/zcode-cli/packages/core/src/subagent/context-builder.ts:106-163`：CLI prefix → `Subagent Agent Prompt`（= profile systemPrompt + 记忆，:117）→ `Subagent Notes`（:128）→ `Subagent Environment`（:134）→ user instructions / currentDate / skills；每段带 cacheControl（:59）。
- 记忆模板（profile 声明 `memory` 时注入）`apps/zcode-cli/packages/core/src/subagent/persistent-memory-prompt.ts:6-140` `PERSISTENT_AGENT_MEMORY_PROMPT_TEMPLATE`（"You have a persistent, file-based memory system at `<MEMORY_ROOT>/` ..."），拼装入口 :150-168。
- 自定义 profile 系统提示 = markdown 正文 `apps/zcode-cli/packages/core/src/subagent/profile.ts:208-212`：`profile: { name, description, source: input.source, systemPrompt: parsed.body.trim(), ... }`（frontmatter 支持 tools/disallowedTools/maxTurns/memory/mcpServers/skills/background/injectAgentsMd 等，:206-226）。

---

## 5. 子 agent 的工具范围

**结论**：**profile 白名单制 + 兜底继承**：`general-purpose` 声明 `tools: ["*"]`，展开为父工具注册表可见工具名（含父 allowlist 过滤后的 MCP 工具）；内置 `Explore` 是固定只读白名单（Bash/Glob/Grep/Read/WebFetch/WebSearch/TodoWrite，无任何写文件工具）。统一强制禁用 `EnterPlanMode`/`ExitPlanMode`；**Agent/Task 派生工具从子工具面剔除，且 child runtime 的 `subagents.enabled: false`，因此子 agent 不能再创建子 agent（深度固定 1 层）**。权限差异：Explore 用独立的 `PermissionService(defaultPermissionConfig)` 且 mode 解析为 `yolo`（免逐调用确认、只读语义靠提示词约束）；general-purpose/自定义继承父权限服务与权限模式（项目级 profile 禁止通过 frontmatter 提权）。另强制附加 `RespondToCoordinator` 控制工具；官方 computer-use（CUA）MCP/工具/Skill 对子 agent 一律拒绝；Skill 按 profile `skills` 过滤；MCP 仅借用父启动快照并可按 `mcpServers` 收窄。workflow child（工作流 actor）另有结构性禁用清单（CreateWorkflow/AmendWorkflow/SaveWorkflow/ResumeWorkflowRun/ResolveWorkflowQuestion——"child 内不得再编排"）。

**证据**：
- 白名单来源 `profile.ts:37` `tools?: readonly string[]`；general-purpose `profile.ts:128` `tools: ["*"]`；Explore `profile.ts:78` `tools: ["Bash", "Glob", "Grep", "Read", "WebFetch", "WebSearch", "TodoWrite"]`；白名单本体 `apps/zcode-cli/packages/core/src/subagent/explore-tools.ts:4-12`（注释 :2-3：`"白名单刻意不含任何文件写工具（Write/Edit/ApplyPatch），因此 Bash 是唯一的副作用入口，只读语义靠 Explore prompt 约束。"`）。
- `"*"` 展开为父工具面（去派生工具）`apps/zcode-cli/packages/core/src/runtime/methods/subagent.ts:499-518`：`const inheritsAvailableTools = request.allowedTools.length === 0 || request.allowedTools.includes("*"); ... return appendCoordinatorResponseTool([...new Set(availableToolNames)].filter((toolName) => !isSubagentDispatchToolName(toolName)).filter(...))`；`compat.ts:12-14` `isSubagentDispatchToolName` = {Agent, Task}。
- 强制禁 plan 工具 `apps/zcode-cli/packages/core/src/subagent/tool-policy.ts:4-13`：`SUBAGENT_CHILD_FORCED_DISALLOWED_TOOLS = [ENTER_PLAN_MODE_TOOL_NAME, EXIT_PLAN_MODE_TOOL_NAME]`（:19-21 注释：`"子 agent 没有独立的 plan approval 恢复面，暴露 plan tools 会让 ExitPlanMode 等待用户确认并卡住父 turn"`）。
- **深度限制 1 层**：`subagent.ts:284-287`：`subagents: { backgroundBashMaxMs: ..., enabled: false, }`（child runtime 配置显式关闭 subagent）→ `subagent.ts:63-65` `if (this.config.subagents?.enabled === false) { return undefined; }`（SubagentPort 不存在）→ 若仍调用 Agent 工具则 `agent.ts:178-191` 抛 `"SubagentPort is not configured for Agent tool"` / `AgentErrorCode.SUBAGENT_UNAVAILABLE`。
- 权限差异 `subagent.ts:315-318`：`// Explore 使用独立只读权限配置；general-purpose 和自定义 agent 继承父权限服务。permissionService: builtInExplore ? new PermissionService(defaultPermissionConfig) : this.permissionService`；`subagent.ts:483-485`：`case undefined: return builtInExplore ? "yolo" : parentMode;`；项目级 profile 禁止提权 `profile.ts:183-185`：`// 项目级 subagent markdown 属于仓库输入，不能通过 frontmatter 把 child runtime 提升到 bypass/yolo`。
- CUA 拒绝 `subagent.ts:834-878` `validateSubagentComputerUseConfiguration`（:864-876 抛 `SUBAGENT_COMPUTER_USE_UNAVAILABLE_MESSAGE`）；Skill 过滤 `subagent.ts:724-832` `FilteredSkillPort`（:757-758 `"Skill is not allowed for subagent"`）；MCP 收窄 `subagent.ts:566-568`（`profile.mcpServers` 限定）。
- `RespondToCoordinator` 强制附加 `subagent.ts:541-548` `appendCoordinatorResponseTool`。
- workflow child 禁用清单 `apps/zcode-cli/packages/core/src/runtime/helpers/tool-allowlist.ts:26-47`：`WORKFLOW_CHILD_DISALLOWED_TOOLS = [CREATE_WORKFLOW, AMEND_WORKFLOW, SAVE_WORKFLOW, RESUME_WORKFLOW_RUN, RESOLVE_WORKFLOW_QUESTION]`（:34-36 注释：`"**结构性禁用**——child 内不得再编排。"`）。

---

## 6. 子 agent 的运行方式

**结论**：前台模式**同步阻塞**——Agent 工具 await 子运行时跑完才返回 tool result；`run_in_background: true` 走**异步**（`start` 在 child session 就绪后立即返回 `async_launched`，完成/失败时以 `<task-notification>` XML 注入父 runtime 命令队列通知父模型，并发 `BackgroundTaskCompleted`/`SubagentStopped` 会话事件）。运行中的前台 agent 可被自动转后台（`autoBackgroundMs` 定时器）或按请求转后台。并发：**未找到 subagent 总数上限**；实际并发受父 turn 工具调度器上限约束（`DEFAULT_MAX_CONCURRENCY = 10`，Agent 元数据 `concurrentSafe: true` 可并行）。超时：Agent 工具本身 `timeout: { kind: "none" }`（无总时长上限），但有**活动看门狗**——默认 600s（`DEFAULT_MODEL_STREAM_IDLE_TIMEOUT_MS = 600_000`）无任何 child 事件即 abort；轮次上限 `maxTurns`（profile 可配，缺省 4）。后续交互：父用 `SendMessage` 给存活/已完成 agent 发消息（queued / resumed_background），子用 `RespondToCoordinator` 主动向父汇报。

**证据**：
- 同步阻塞 `agent.ts:211-221`：`return context.subagentPort.launch({...}, { signal: context.abortSignal, ... })`；`runner.ts:170`：`return port.run(executionRequest, launchOptions);`，run 内 `runner.ts:309-316` `await Promise.race([guardedCompletionPromise..., backgroundRequestPromise..., autoBackgroundTimer...])` 后 `:381 return completed.output;`。
- 异步后台 `runner.ts:439-526` `start(...)`：注册 task → `void runBackgroundAgent(...)`（:470）→ `await readyGate.promise`（:509）→ `return output;`（:525，即 `createAgentBackgroundedOutput`，:1476-1492 `{ status: "async_launched", isAsync: true, agentId, childSessionId, backgroundTaskId, outputFile, canReadOutputFile }`）。
- 前台自动转后台 `runner.ts:291-316`：`autoBackgroundTimer = ... createAutoBackgroundTimer(registry, lifecycle.agentId, autoBackgroundMs, ...)` 与 `registry.waitForBackgroundRequest(...)` 参与 `Promise.race`；配置项 `apps/zcode-cli/packages/core/src/runtime/types.ts:142` `autoBackgroundMs?: number;`（同 :140-145 `inactivityTimeoutMs / backgroundBashMaxMs / maxTurns / outputRootDir`）。
- 并发：`apps/zcode-cli/packages/core/src/tool/scheduler.ts:48` `const DEFAULT_MAX_CONCURRENCY = 10;`（父 turn 内并行工具调用上限，含并行 Agent 派生）；`agent.ts:231` `concurrentSafe: true`；**未找到** subagent 数量/嵌套并发的专门上限。
- 超时：`agent.ts:267` `timeout: { kind: "none" }`；看门狗 `runner.ts:208-215` `createSubagentActivityWatchdog({ ..., timeoutMs: options.inactivityTimeoutMs ?? DEFAULT_MODEL_STREAM_IDLE_TIMEOUT_MS, })`，触发 `runner.ts:1226-1241` `createCoreError(CoreErrorType.ToolTimeout, \`Subagent was inactive for ${options.timeoutMs}ms\`, ...)`；默认值 `apps/zcode-cli/packages/contracts/src/config/index.ts:284` `export const DEFAULT_MODEL_STREAM_IDLE_TIMEOUT_MS = 600_000;`；轮次上限 `subagent.ts:269` `maxTurns: request.maxTurns ?? this.config.subagents?.maxTurns ?? 4,`。
- 结果通知回父：`runner.ts:1505-1517` `formatLocalAgentTaskNotification({... result: completed.output.content.map(...).join("\n\n") ...})` → `runner.ts:1830-1895` `enqueueBackgroundNotification`（幂等去重 `task.notified`，:1848-1857）→ `subagent.ts:79-87` `enqueueParentTaskNotification: (notification) => { this.enqueueBackgroundTaskNotification({...}); }`（父 runtime 命令队列）；通知格式 `apps/zcode-cli/packages/core/src/runtime-task/notification.ts:144-158` `<task-notification><task-id>/<tool-use-id>/<output-file>/<status>/<summary>/<result>/<error>/<usage></task-notification>`，总长截断 120k 字符（:18 `TASK_NOTIFICATION_MAX_CHARS = 120_000`，:380-383 `truncateTaskNotification`）。完成事件 `runner.ts:1542-1559`（`SessionEventType.SubagentStopped`）与 `:1741-1768`（`BackgroundTaskCompleted`）发到父会话。
- 追问/续聊：`send-message.ts:25-35`（工具描述：`"To resume a completed agent, use its agentId; it resumes in the background and you'll be notified when it finishes."`）；投递语义 `runner.ts:1086-1091`（`queued` / `resumed_background` / 直送 running turn）；子→父主动汇报 `apps/zcode-cli/packages/core/src/subagent/coordinator-response.ts:23-41`（`RespondToCoordinator` → `enqueue` 到父队列）。

---

## 关键源码文件清单

| 文件（绝对路径） | 职责 |
|---|---|
| `/Users/apple/Desktop/code/ZCode/apps/zcode-cli/packages/core/src/tool/handlers/agent.ts` | Agent 工具入口（含 Task 别名）、工具描述、结果格式化/预算 |
| `/Users/apple/Desktop/code/ZCode/apps/zcode-cli/packages/contracts/src/tools/agent.ts` | 输入/输出 schema（AgentInputSchema / AgentCompletedOutput / AgentBackgroundedOutput） |
| `/Users/apple/Desktop/code/ZCode/apps/zcode-cli/packages/contracts/src/interfaces/subagent.port.ts` | SubagentPort 接口与运行请求/选项类型 |
| `/Users/apple/Desktop/code/ZCode/apps/zcode-cli/packages/core/src/subagent/runner.ts` | 子 agent 生命周期：前台/后台、registry、看门狗、artifact、通知、SendMessage 续跑 |
| `/Users/apple/Desktop/code/ZCode/apps/zcode-cli/packages/core/src/runtime/methods/subagent.ts` | 子运行时装配：工具面、权限、MCP/Skill 借用、模型继承、AgentRuntime 构造 |
| `/Users/apple/Desktop/code/ZCode/apps/zcode-cli/packages/core/src/subagent/profile.ts` | AgentProfile 定义、内置 profile、markdown frontmatter 解析 |
| `/Users/apple/Desktop/code/ZCode/apps/zcode-cli/packages/core/src/subagent/general-purpose.ts` | general-purpose 系统提示词模板 |
| `/Users/apple/Desktop/code/ZCode/apps/zcode-cli/packages/core/src/subagent/explore.ts` | Explore 系统提示词模板（只读） |
| `/Users/apple/Desktop/code/ZCode/apps/zcode-cli/packages/core/src/subagent/explore-tools.ts` | Explore 工具白名单 |
| `/Users/apple/Desktop/code/ZCode/apps/zcode-cli/packages/core/src/subagent/tool-policy.ts` | 子 agent 强制禁用工具（plan 工具） |
| `/Users/apple/Desktop/code/ZCode/apps/zcode-cli/packages/core/src/subagent/system-prompt.ts` | 公共 Notes + 环境上下文 |
| `/Users/apple/Desktop/code/ZCode/apps/zcode-cli/packages/core/src/subagent/context-builder.ts` | 子 agent 上下文/system 组装 |
| `/Users/apple/Desktop/code/ZCode/apps/zcode-cli/packages/core/src/subagent/persistent-memory.ts` / `persistent-memory-prompt.ts` | profile 级持久记忆加载与提示词模板 |
| `/Users/apple/Desktop/code/ZCode/apps/zcode-cli/packages/core/src/subagent/tool-event-mirror.ts` | child 工具/权限事件镜像到父会话 |
| `/Users/apple/Desktop/code/ZCode/apps/zcode-cli/packages/core/src/subagent/completion-notification.ts` | 后台完成通知文案 |
| `/Users/apple/Desktop/code/ZCode/apps/zcode-cli/packages/core/src/runtime-task/notification.ts` | `<task-notification>` XML 格式与 120k 截断 |
| `/Users/apple/Desktop/code/ZCode/apps/zcode-cli/packages/core/src/subagent/coordinator-response.ts` | 子→父 RespondToCoordinator 通道 |
| `/Users/apple/Desktop/code/ZCode/apps/zcode-cli/packages/core/src/tool/handlers/send-message.ts` | 父→子 SendMessage 工具 |
| `/Users/apple/Desktop/code/ZCode/apps/zcode-cli/packages/core/src/tool/compat.ts` | Agent/Task 派生工具名判定 |
| `/Users/apple/Desktop/code/ZCode/apps/zcode-cli/packages/core/src/runtime/helpers/tool-allowlist.ts` | workflow child 结构性禁用清单、allowlist 归一 |
| `/Users/apple/Desktop/code/ZCode/apps/zcode-cli/packages/core/src/tool/scheduler.ts` | 工具调用并发上限（10） |
| `/Users/apple/Desktop/code/ZCode/apps/zcode-cli/packages/contracts/src/config/index.ts` | `DEFAULT_MODEL_STREAM_IDLE_TIMEOUT_MS = 600_000` |
| `/Users/apple/Desktop/code/ZCode/apps/zcode-cli/packages/tui/SUBAGENTS.md` | TUI 子 agent 观测/隔离设计约定 |
| （第二路径）`/Users/apple/Desktop/code/ZCode/apps/zcode-cli/packages/core/src/tool/handlers/create-workflow-description.ts`、`/Users/apple/Desktop/code/ZCode/apps/zcode-cli/packages/dynamic-workflow/src/engine/{engine.ts,scheduler.ts,concurrency.ts}`、`/Users/apple/Desktop/code/ZCode/apps/zcode-cli/packages/dynamic-workflow-runtime/src/harness.ts` | Dynamic Workflow：脚本化多 subagent 编排（fan-out/并发/事件） |
