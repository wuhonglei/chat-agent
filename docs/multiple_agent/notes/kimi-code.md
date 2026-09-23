# kimi-code 多 Agent / 子 Agent（Subagent）实现方案分析

> 代码库：`/Users/apple/Desktop/code/kimi-code`（pnpm monorepo：`apps/`（kimi-code CLI、vscode、vis）+ `packages/`（agent-core-v2 核心、klient、node-sdk、acp-server 等））
> 核心实现位于 `packages/agent-core-v2`；CLI（apps/kimi-code）与 SDK（packages/node-sdk、packages/klient）只是消费方。
> 分析日期：2026-09-22。所有行号以当时文件内容为准。

总体架构一句话：kimi-code 没有"调度器/隐式拆分"，子 agent 完全由 **LLM 主动调用工具** 派生——单个用 `Agent` 工具、批量用 `AgentSwarm` 工具、多 agent 编排（git worktree 隔离）用 `TowerSpawn` 工具；子 agent 是**同进程的独立 agent loop 实例**（独立上下文、独立 wire 持久化文件），通过 `SessionSubagentService` 创建/派生、`runAgentTurn` 驱动、`AgentTaskService` 管理前后台与超时，结果以「最后一条 assistant 文本」回传给父。

---

## 1. 创建子 agent 的时机

**结论**：派生完全是**工具调用触发**（LLM 决定），没有后台调度器、也没有框架自动拆分任务的机制。三个入口工具：
1. `Agent`（单个子 agent，`SubagentTool`）——工具名硬编码 `name: string = 'Agent'`；
2. `AgentSwarm`（一次批量派生最多 128 个同构子 agent）；
3. `TowerSpawn`（Tower 多 agent 编排模式下派生 worker/reviewer 子 agent，git worktree 隔离，属可选 feature）。

调用链：`SubagentTool.execution()` → `SessionSubagentService.planSpawn()` / `.spawn()` / `.run()` → `runAgentTurn()` 提交一轮 prompt 启动子 loop。此外 `Agent(resume="<agent_id>")` 可复活既有子 agent 而非新建。没有任何"当上下文过长自动派生子 agent"之类的隐式触发。

**证据**：
- `packages/agent-core-v2/src/agent/tools/agent/agentTool.ts:106-108`
  ```ts
  export class SubagentTool implements ISubagentTool {
    readonly name: string = 'Agent';
  ```
- `packages/agent-core-v2/src/agent/tools/agent/agentTool.ts:682-686`
  ```ts
  registerAgentToolService(ISubagentTool, SubagentTool, {
    name: 'Agent', domain: 'subagent', requiredRuntimeCapabilities: ['process'],
  });
  ```
- `packages/agent-core-v2/src/agent/tools/agent/agentTool.ts:353-378`（planSpawn→spawn→run 调用链）
  ```ts
  const plan = await this.subagents.planSpawn({ callerAgentId: this.callerAgentId, ... });
  const spawned = await this.subagents.spawn({ callerAgentId: this.callerAgentId, plan, labels: subagentLabels(this.callerAgentId), prompt: args.prompt });
  ...
  const run = await this.subagents.run(target.accessor.get(IAgentScopeContext).agentContext,
    { kind: 'prompt', prompt: promptText }, { signal: controller.signal });
  ```
- 批量入口：`packages/agent-core-v2/src/features/swarm/tools/agent-swarm/agentSwarmTool.ts:72-74`
  ```ts
  export class AgentSwarmTool implements IAgentSwarmTool {
    readonly name = 'AgentSwarm' as const;
  ```
- Tower 入口：`packages/agent-core-v2/src/features/tower/tools/spawn/spawnTool.ts:57-61`
  ```ts
  export class TowerSpawnTool implements ITowerSpawnTool {
    readonly name = 'TowerSpawn' as const;
  ```
- 真正启动子 loop：`packages/agent-core-v2/src/session/subagent/runAgentTurn.ts:41-45`
  ```ts
  const { id } = request.kind === 'prompt'
    ? loop.submit({ message: { role: 'user', content: [{ type: 'text', text: request.prompt }] },
        meta: { origin: AGENT_RUN_PROMPT_ORIGIN, tracked: true } })
  ```
  其中 `AGENT_RUN_PROMPT_ORIGIN = { kind: 'system_trigger', name: 'subagent' }`（同文件 19-22 行）。

---

## 2. 子 agent 的上下文管理

**结论**：
- **继承什么**：默认（非 fork）**零上下文**——子 agent 看不到父的对话历史，只拿到工具参数里写好的 `prompt`；系统提示词按子 agent 自己的 profile 渲染（不是复制父的）。但会继承：**权限模式**（`setMode(caller.mode)`）、**用户自定义工具**（`inheritUserTools(callerUserTools)`）、**会话级工作目录**（同一 `sessionContext.cwd`，各自有独立 homedir）。模型默认继承调用者模型（可经 `[secondary_model]` 池覆盖）。
- **fork 模式**（实验 flag `subagent_fork`）：`fork: true` 时调用 `agentLifecycle.fork()`，把父**完整已完成对话历史快照**拷入子 agent 的 contextMemory（尾部未闭合的工具调用会被闭合），并在开头注入一段免责声明（"这不是你自己的历史，只作参考"）。
- **隔离**：每个子 agent 是独立 DI scope（`agents/{agentId}`）+ 独立 `WireService`（独立 wire 落盘文件）+ 独立 contextMemory / task 持久化目录，父子上下文互不可见。
- **回传**：只回传子 agent **最后一条 assistant 消息的纯文本**作为 `summary`（原样文本，不做 LLM 摘要；stop reason 文本截断到 2000 字符）。父的系统提示也明说"main agent 看不到你的上下文，只能看到你最后一条消息"。后台任务完成时输出整体持久化到文件，通知里只带预览或文件指针（间接截断）。

**证据**：
- 零上下文约定：`packages/agent-core-v2/src/agent/tools/agent/agent.md:4`
  > "The subagent starts with zero context — it has not seen this conversation. Brief it like a colleague who just walked into the room"
- fork 历史拷贝：`packages/agent-core-v2/src/session/agentLifecycle/agentLifecycleService.ts:447-452`
  ```ts
  const sourceMessages = source.accessor.get(IAgentContextMemoryService)?.get();
  if (sourceMessages !== undefined && sourceMessages.length > 0) {
    child.accessor.get(IAgentContextMemoryService)?.append(...closeTrailingOpenToolExchange(sourceMessages));
  }
  ```
- fork 免责声明：`packages/agent-core-v2/src/session/subagent/spawn.ts:13-14`
  ```ts
  export const FORK_CONTEXT_NOTICE =
    'The conversation above is not your own history: it is a one-time snapshot inherited from the agent that forked you. Treat it as reference material only ...';
  ```
  注入位置：`packages/agent-core-v2/src/session/subagent/subagentService.ts:157-164`（`agentLifecycle.fork(...)` 后 `IAgentReminderService.notify(FORK_CONTEXT_NOTICE, ...)`）。
- 继承权限模式与用户工具：`packages/agent-core-v2/src/session/subagent/subagentService.ts:184-194`
  ```ts
  created.accessor.get(IAgentPermissionModeService)
    .setMode(caller.accessor.get(IAgentPermissionModeService).mode);
  ...
  createdUserTools.inheritUserTools(callerUserTools);   // fork 时限定为 activeToolNames
  ```
- 共享工作目录：`packages/agent-core-v2/src/session/subagent/subagentService.ts:221-223`（`promptPrefix` 用 `workDir: this.sessionContext.cwd`，即会话 cwd）。
- 上下文隔离（独立 scope / wire / homedir）：`packages/agent-core-v2/src/session/agentLifecycle/agentLifecycleService.ts:248-249`
  ```ts
  const agentScope = this.ctx.scope(`agents/${agentId}`);
  const agentHomedir = join(this.bootstrap.homeDir, agentScope);
  ```
  同文件 275-282 每个 agent 新建独立 `WireService`；task 持久化也按 agent 分目录：`packages/agent-core-v2/src/agent/task/taskService.ts:245-248`（`join(session.sessionDir, 'agents', this.scopeContext.agentId)`）。
- 回传 = 最后一条 assistant 文本：`packages/agent-core-v2/src/session/subagent/runAgentTurn.ts:73`
  ```ts
  const summary = latestAssistantText(target.accessor.get(IAgentContextMemoryService).get());
  ```
  `latestAssistantText`（同文件 169-176）从消息数组尾部向前找第一条 assistant 文本并拼接 text part（不做摘要、按原文返回；超过 stop-reason 的 2000 字符截断只作用于错误原因，见 `agentTool.ts:620` `REASON_MAX_CHARS = 2000`）。
- 父只能看到最后一条消息（写进子 agent 系统提示）：`packages/agent-core-v2/src/app/agentProfileCatalog/profile-shared.ts:14-18`
  ```ts
  export const TASK_AGENT_ROLE_PREFIX =
    'You are now running as a subagent. All the `user` messages are sent by the main agent. ' +
    'The main agent cannot see your context, it can only see your last message when you finish the task. ...';
  ```
- 后台任务输出持久化 + 通知只带预览/文件指针：`packages/agent-core-v2/src/agent/task/taskService.ts:1398-1411`（`agentTaskNotificationChildren`：完整输出给 `<output-file path=...>`，否则 `<output-preview ... truncated=...>`）。

---

## 3. 子 agent 的输入输出内容

**结论**：
- **输入**（`Agent` 工具的 zod schema）：`prompt`（完整任务描述，必填）、`description`（3-5 词短描述，UI 用，必填）、`subagent_type`（profile 名，默认 `coder`）、`resume`（既有 agent_id，续跑）、`run_in_background`（布尔）、`fork`（布尔，实验）、`model`（secondary model 池别名或 `primary`）。**没有附件字段**——文件路径/命令要求写进 `prompt` 文本；若 profile 配了 `promptPrefix`（如 explore 的 git 上下文），会被前置到 prompt。内部运行请求则是 `AgentRunRequest = { kind:'prompt', prompt:string } | { kind:'retry' }`。
- **AgentSwarm 输入**：`description`、`subagent_type`、`prompt_template`（含 `{{item}}` 占位符）、`items[]`、`resume_agent_ids`（record: agentId→prompt）、`fork`、`model`。
- **输出**：结构化定义为 `SubagentToolOutput = { result: string, usage: {...token 计数} }`，但父模型实际看到的是**格式化纯文本**：成功时 `agent_id/actual_subagent_type/status/stop_reason` + `[summary]`（子 agent 最终 assistant 文本）+ `resume_hint` + 可选 `next_step`；后台则返回 `task_id/status: running/agent_id/.../resume_hint`。Swarm 输出为 `<agent_swarm_result>` XML（每子 agent 一个 `<subagent ...>文本</subagent>`）。结果不落成文件给父（子 agent 自己改的代码文件除外），后台任务的原始输出会持久化为输出文件供 `TaskOutput` 读取。

**证据**：
- 输入 schema：`packages/agent-core-v2/src/agent/tools/agent/agent.ts:29-62`
  ```ts
  z.object({
    prompt: z.string().describe('Full task prompt for the subagent'),
    description: z.string().describe('Short task description (3-5 words) for UI display'),
    subagent_type: z.string().optional()...,
    resume: z.string().optional().describe('Optional agent ID to resume instead of creating a new instance...'),
    run_in_background: z.boolean().optional()...,
    fork: z.boolean().optional()...,
    model: z.string().optional()...,
  })
  ```
- 输出 schema：`packages/agent-core-v2/src/agent/tools/agent/agent.ts:67-77`
  ```ts
  export const SubagentToolOutputSchema = z.object({
    result: z.string().describe('Aggregated text output from the subagent'),
    usage: z.object({ input: ..., output: ..., cache_read?..., cache_write?... }).describe('Cumulative token usage'),
  });
  ```
- 前台成功结果格式：`packages/agent-core-v2/src/agent/tools/agent/agentTool.ts:756-773`
  ```ts
  const lines = [`agent_id: ${handle.agentId}`, `actual_subagent_type: ${handle.profileName}`,
    'status: completed', `stop_reason: ${reason}`];
  ...
  lines.push('', '[summary]', result, '', resumeHint(handle.agentId, '...'));
  ```
- 后台结果格式：同文件 732-754（`task_id: ...`、`status: running`、`automatic_notification: true`、`resume_hint: ...`）。
- Swarm 输入 schema：`packages/agent-core-v2/src/features/swarm/tools/agent-swarm/agent-swarm.ts:6-58`（`PROMPT_TEMPLATE_PLACEHOLDER = '{{item}}'`，`items`、`prompt_template`、`resume_agent_ids: z.record(...)` 等）。
- Swarm 输出 XML：`packages/agent-core-v2/src/features/swarm/tools/agent-swarm/agentSwarmTool.ts:303-328`
  ```ts
  '<agent_swarm_result>', `<summary>${...}</summary>`, ...
  `<subagent${mode}${agentId}${item}${state} outcome="${result.status}"${stopReason}>${body}</subagent>`
  ```
- prompt 前置（promptPrefix）：`packages/agent-core-v2/src/session/subagent/subagentService.ts:195-197、214-228`（`applyProfilePromptPrefix(profile, prompt, ...)`；explore profile 的 prefix 是 git 上下文，见第 4 节）。

---

## 4. 子 agent 的系统提示词

**结论**：系统提示词 = **共享模板 `system.md`** + **profile 角色前缀（`role_additional`）** 渲染而成。模板文件在 `packages/agent-core-v2/src/app/agentProfileCatalog/system.md`；子 agent 特有的角色前缀常量 `TASK_AGENT_ROLE_PREFIX` 与渲染函数在 `profile-shared.ts`；各 profile（`agent`/`coder`/`explore`）的注册与角色文本在 `packages/agent-core-v2/src/session/agentLifecycle/profile/profiles.ts`。核心差异点：子 agent 被告知"你现在是 subagent，user 消息都来自 main agent，父只能看到你最后一条消息，把父当调用方、不要直接问最终用户、有歧义写进最终 summary"；coder 另加"最终消息就是全部交接内容"的 handoff 要求；explore 叠加只读约束 overlay（`explore-overlay.md`）。工具描述（非系统提示但同为提示面）在 `agent.md` / `agent-swarm.md` 等 md 文件里以 `?raw` 内联。

**证据**：
- 模板引用：`packages/agent-core-v2/src/app/agentProfileCatalog/profile-shared.ts:12`
  ```ts
  import SYSTEM_PROMPT_TEMPLATE from './system.md?raw';
  ```
  渲染：同文件 190-201（`renderPrompt(SYSTEM_PROMPT_TEMPLATE, { ...systemPromptVars(...), role_additional: roleAdditional })`）。
- 子 agent 角色前缀：`packages/agent-core-v2/src/app/agentProfileCatalog/profile-shared.ts:14-18`
  > `'You are now running as a subagent. All the `user` messages are sent by the main agent. The main agent cannot see your context, it can only see your last message when you finish the task. You must treat the parent agent as your caller. Do not directly ask the end user questions. If something is unclear, explain the ambiguity in your final summary to the parent agent.'`
- coder 角色：`packages/agent-core-v2/src/session/agentLifecycle/profile/profiles.ts:82-88`
  ```ts
  const CODER_ROLE =
    `${TASK_AGENT_ROLE_PREFIX}\n\n` +
    'Your final message is the entire handoff — the parent sees nothing else from your run. ' +
    'Make it technically complete: what you changed and why, the path of every file you touched, ' +
    'how you verified the change (tests or commands run, with results), and anything left undone ' +
    'or worth follow-up. ...';
  ```
- 模板开头（`system.md:1-5`）：
  > "You are ${product_name}, an interactive general AI agent running on a user's computer. Your primary goal is to help users with software engineering tasks. ${role_additional}"
- 模板环境段（`system.md:59`）：
  > "The environment is not a sandbox: your actions take effect on the user's system immediately."
- explore 的 promptPrefix（git 上下文）与只读 overlay：`packages/agent-core-v2/src/session/agentLifecycle/profile/profiles.ts:110-125`（`promptPrefix: async ({ cwd, process, log }) => collectGitContext(...)`）+ `packages/agent-core-v2/src/session/agentLifecycle/profile/explore-overlay.md:15`（"Use Bash ONLY for read-only operations (ls, git status, git log, git diff, find)"）。
- 另有 NotifyUser 指引里专门的 subagent 段落：`packages/agent-core-v2/src/app/agentProfileCatalog/profile-shared.ts:112-113`（"If you are working as a subagent, report only your own subtask's progress ... Updates do not automatically reach your parent agent: include every important finding in your final handoff."）。

---

## 5. 子 agent 的工具范围

**结论**：**按 profile 白名单裁剪，不是继承父的工具集**。每个 agent profile 声明 `tools`（及可选 `disallowedTools`）：`coder`（默认子 agent 类型）有读写/编辑/Bash/mcp__* 等但**没有 `Agent`/`AgentSwarm`**；`explore` 只有只读工具（Bash 仅提示词约束只读，无硬沙箱）。**递归深度实际上被双保险限制为 2 层**：(a) 内置子 profile 工具表里根本没有派生工具；(b) 即使自定义 profile 有 `Agent` 工具，父在 `planSpawn` 时会用 `withoutDelegatingTargets` 从可派生类型列表中剔除"自己还能再派生"的类型（调用者 profile 未声明 `subagents` 字段时）。只有 `agent`（主 agent）profile 声明了 `subagents: ['coder','explore','plan']`。**无沙箱差异**：子 agent 与父同进程、同样直接作用于用户机器；差异只在权限模式镜像、用户工具继承、运行时能力要求（`requiredRuntimeCapabilities: ['process']`）。

**证据**：
- profile 工具白名单：`packages/agent-core-v2/src/session/agentLifecycle/profile/profiles.ts:46-69`（`CODER_TOOLS`，无 `Agent`/`AgentSwarm`）、71-80（`EXPLORE_TOOLS` 仅 `NotifyUser/Bash/Read/ReadMediaFile/Glob/Grep/WebSearch/FetchURL`）、11-44（`AGENT_TOOLS` 含 `'Agent', 'AgentSwarm'`）。
- 只有主 profile 声明可派生类型：同文件 90-97
  ```ts
  registerAgentProfile({ name: 'agent', ..., tools: AGENT_TOOLS,
    subagents: ['coder', 'explore', 'plan'], ... });
  ```
- 派生目标过滤（防递归）：`packages/agent-core-v2/src/app/agentProfileCatalog/profile-shared.ts:75-94`
  ```ts
  export function profileCanDelegate(profile): boolean {
    const possesses = (name) => (profile.tools === undefined || profile.tools.includes(name)) && !(profile.disallowedTools ?? []).includes(name);
    return possesses('Agent') || possesses('AgentSwarm');
  }
  export function withoutDelegatingTargets(catalog, allowlist) {
    return allowlist.filter((name) => { const target = catalog.get(name);
      return target === undefined || !profileCanDelegate(target); });
  }
  ```
  应用于 spawn 规划：`packages/agent-core-v2/src/session/subagent/subagentService.ts:104-107`
  ```ts
  let allowlist = subagentAllowlistFor(this.catalog, own, extras);
  if (allowlist !== undefined && own.subagents === undefined) {
    allowlist = withoutDelegatingTargets(this.catalog, allowlist);
  }
  ```
- 类型白名单：`packages/agent-core-v2/src/app/agentProfileCatalog/profile-shared.ts:24-38`（`subagentAllowlistFor`；`['*']` 表示不限）；越界报错同文件 96-102。
- 工具过滤还叠加外部 toolPolicy：`packages/agent-core-v2/src/agent/tools/agent/agentTool.ts:171-186`（`profile.tools?.filter(...)` + `isToolActiveForProfile`，`ReadMediaFile` 还要求模型具备 image/video 输入能力）。
- 权限/用户工具：见第 2 节 `subagentService.ts:184-194`（权限模式镜像 + `inheritUserTools`）。
- 无沙箱：`agent.md:1`（"runs as a same-process loop instance with its own context and wire file"）+ `system.md:59`（"The environment is not a sandbox"）。explore 的只读是 **prompt-enforced**（`profiles.ts:112` "Fast codebase exploration with prompt-enforced read-only behavior."），非硬性。
- 运行时能力要求（相当于"沙箱/权限差异"的唯一硬约束）：`agentTool.ts:685`（`requiredRuntimeCapabilities: ['process']`）；spawn 时还要先拿到 process 运行时租约：`subagentService.ts:151-153`（`acquire(['process'])`，fork 除外）。
- 深度限制小结：内置 profile 下派生深度 = 2（main → coder/explore，coder/explore 无法再派生）；自定义 profile 若想可再派生需自带 `Agent` 工具且其父 profile 显式声明 `subagents`，代码未见硬编码的固定层数常量（未找到全局 max-depth 常量——限制是结构性的）。

---

## 6. 子 agent 的运行方式

**结论**：
- **前台（默认）同步阻塞**：`Agent` 工具把子 agent 注册为一个前台 task（`detached: false`），然后 `await tasks.waitForForegroundRelease(taskId)` 阻塞该工具调用直到子 agent 终结，直接把结果文本作为工具输出返回。用户中断会级联 abort 子 agent。
- **后台异步**（`run_in_background: true`）：注册为 detached task 立即返回 `task_id`，完成后通过 `loop.notify()` 注入**合成 user 角色消息**（内容是 `<notification ...>` XML，含输出预览/输出文件指针）自动出现在父的后续 turn——不需要父轮询；配套 `TaskList`/`TaskOutput`/`TaskStop`/`WaitFor` 工具可选查/停。后台模式仅当这三个管理工具启用时可用。
- **并发**：`AgentSwarm` 最多 128 个子 agent；启动节奏限流（首 5 个立即、之后约每 700ms 一个），可选 `KIMI_CODE_AGENT_SWARM_MAX_CONCURRENCY` 设并发上限；无默认硬并发上限（仅排队节流）。后台（detached）任务总数受 `[task].maxRunningTasks`（env `KIMI_CODE_BACKGROUND_MAX_RUNNING_TASKS`）限制，超限报 `TASK_LIMIT_EXCEEDED`。
- **超时**：默认 **2 小时**（`DEFAULT_SUBAGENT_TIMEOUT_MS = 2*60*60*1000`，`[subagent].timeoutMs` 或 env `KIMI_SUBAGENT_TIMEOUT_MS`）；swarm 有独立 `[swarm].timeoutMs`（默认同 2h）。超时后 task 被终止并置 `timed_out`，前台回传 "Agent timed out after ..."；另有 per-turn step cap（maxSteps）和 max_tokens 防线。Swarm 遇 provider 限流会自动退避重排队（requeue + retry）。
- **结果通知回父**：前台 = 工具返回值即时回传；后台 = 合成 `<notification>` user 消息自动送达；两种场景都派发内部事件（`subagent.spawned/started/completed/failed/cancelled`）供 UI（TUI/vscode）展示；失败/超时结果里附 `resume_hint`，可用 `Agent(resume="<agent_id>")` 续跑（子 agent 上下文跨 session 保留）。

**证据**：
- 前台阻塞 / 后台立即返回：`packages/agent-core-v2/src/agent/tools/agent/agentTool.ts:566-578`
  ```ts
  if (runInBackground) {
    return { output: formatBackgroundAgentResult(taskId, handle, args.description, allowBackground, false) };
  }
  const release = await this.tasks.waitForForegroundRelease(taskId);
  ```
  前台 task 注册（`detached: runInBackground`）：同文件 519-527。
- 后台可用性取决于 Task 管理工具：`agentTool.ts:143-146`
  ```ts
  this.canRunInBackground = () => this.toolPolicy.isToolActive('TaskList') && this.toolPolicy.isToolActive('TaskOutput') && this.toolPolicy.isToolActive('TaskStop');
  ```
- 完成后合成 user 消息通知父：`packages/agent-core-v2/src/agent/task/taskService.ts:1112-1118`
  ```ts
  const handle = this.loop.notify({
    message: { role: 'user', content: [...context.content], toolCalls: [], origin: context.origin },
    turnScoped: false, ...
  ```
  XML 格式：`packages/agent-core-v2/src/agent/task/notificationXml.ts:17`（`<notification id="..." category="..." type="..." source_kind="background_task" source_id="...">`）。工具描述印证：`packages/agent-core-v2/src/agent/tools/agent/agent-background-enabled.md:1`（"The completion arrives in a later turn as a synthetic user-role message containing its result — you do not need to poll"）。
- Swarm 数量上限：`packages/agent-core-v2/src/features/swarm/tools/agent-swarm/agent-swarm.ts:7`（`export const MAX_AGENT_SWARM_SUBAGENTS = 128;`）；超限拒绝：`agentSwarmTool.ts:231-236`。
- 启动节流与并发上限：`packages/agent-core-v2/src/features/swarm/session/agentRunBatch.ts:39-40`
  ```ts
  const INITIAL_LAUNCH_LIMIT = 5;
  const INITIAL_LAUNCH_INTERVAL_MS = 700;
  ```
  同文件 47（`AGENT_SWARM_MAX_CONCURRENCY_ENV = 'KIMI_CODE_AGENT_SWARM_MAX_CONCURRENCY'`）、662-676（`resolveSwarmMaxConcurrency`）；装配处 `packages/agent-core-v2/src/features/swarm/session/sessionSwarmService.ts:127-128`（`new AgentRunBatch(launcher, linkedTasks, { maxConcurrency }).run()`）。限流重试：`agentRunBatch.ts:412-447`（`requeueRateLimited`，指数退避 `RATE_LIMIT_RETRY_BASE_MS=3000, factor=2`）。
- 后台任务数上限：`packages/agent-core-v2/src/agent/task/taskService.ts:905-913`
  ```ts
  private assertCanRegister(detached: boolean): void {
    const maxRunningTasks = resolveAgentTaskConfig(this.config)?.maxRunningTasks;
    ...
    throw new Error2(ErrorCodes.TASK_LIMIT_EXCEEDED, 'Too many background tasks are already running.', ...);
  ```
  配置项：`packages/agent-core-v2/src/agent/task/configSection.ts:20`（`maxRunningTasks: z.number().int().min(1).optional()`）、47（`MAX_RUNNING_TASKS_ENV = 'KIMI_CODE_BACKGROUND_MAX_RUNNING_TASKS'`）。
- 超时：`packages/agent-core-v2/src/session/subagent/configSection.ts:50-52`
  ```ts
  export const DEFAULT_SUBAGENT_TIMEOUT_MS = 2 * 60 * 60 * 1000;
  export const SUBAGENT_TIMEOUT_ENV = 'KIMI_SUBAGENT_TIMEOUT_MS';
  ```
  超时终止：`taskService.ts:665-677`（`armManagerTimeout` → `terminateWithGrace(..., finalStatus: 'timed_out')`）；swarm 超时：`features/swarm/configSection.ts:19-21`（`DEFAULT_SWARM_TIMEOUT_MS = 2h`，env `KIMI_CODE_SWARM_TIMEOUT_MS`）。错误分类含 `max_tokens`/`max_steps`/`timed_out` 等：`agentTool.ts:607-618`。
- 内部事件流：`packages/agent-core-v2/src/session/subagent/mirrorAgentRun.ts:33-60`（`SubagentSpawned/Started/Completed(resultSummary)/Failed/Cancelled` 事件类）。

---

## 补充：其他相关机制（简述）

- **`Tower`（features/tower）**：多 agent 编排 feature，`TowerSpawn` 派生 `tower-worker` profile 子 agent（`packages/agent-core-v2/src/features/tower/tower.ts:16` `TOWER_WORKER_PROFILE = 'tower-worker'`），在独立 **git worktree** 中做 mission，产出通过 tower 协议文件（TowerReview/TowerFinding）回流——这是唯一带"文件系统级隔离（worktree）"的子 agent 变体（`features/tower/tools/spawn/spawn.md`）。
- **resume 语义**：子 agent 的对话历史跨 session 保留，`Agent(resume="<agent_id>", prompt=...)` 重建 agent scope 后继续（`agentTool.ts:405-460` `resolveResumeTarget`/`rebuildSubagent`）；同一子 agent 不允许并发运行（同文件 429-435 报 `AGENT_ALREADY_RUNNING`）。
- **SDK 面**：`packages/node-sdk/src/task.ts:1-10` 只是把 `SubagentTaskInfo` 等类型 re-export（`AgentBackgroundTaskInfo = SubagentTaskInfo`）；`packages/klient/src/contract/agent/schemas.ts:208` 有 `subagentType` 字段——SDK 未提供独立的派生 API，派生只发生在 agent 工具调用内部。
- **hooks**：`onWillStartAgentTask` / `onDidStopAgentTask` 插件钩子可在子 agent 启动前/停止后介入（`packages/agent-core-v2/src/session/subagent/subagent.ts:36-49`；执行点 `mirrorAgentRun.ts:185-189、208-211`）。

---

## 关键源码文件清单

| 文件（均相对 `/Users/apple/Desktop/code/kimi-code`） | 作用 |
|---|---|
| `packages/agent-core-v2/src/agent/tools/agent/agentTool.ts` | `Agent` 工具（SubagentTool）：派生/续跑/前后台调度、结果格式化 |
| `packages/agent-core-v2/src/agent/tools/agent/agent.ts` | `Agent` 工具输入/输出 schema 与常量 |
| `packages/agent-core-v2/src/agent/tools/agent/agent.md`（+ `agent-background-*.md`、`agent-fork.md`） | `Agent` 工具描述（prompt 写法指南、后台/ fork 语义） |
| `packages/agent-core-v2/src/agent/tools/agent/subagent-task.ts` | 子 agent 作为后台 task 的适配器（SubagentTask/SubagentHandle） |
| `packages/agent-core-v2/src/session/subagent/subagentService.ts` | `SessionSubagentService`：planSpawn/spawn/run 核心编排 |
| `packages/agent-core-v2/src/session/subagent/subagent.ts` | 接口定义（AgentRunRequest/AgentRunCompletion/hook 类型） |
| `packages/agent-core-v2/src/session/subagent/spawn.ts` | spawn 计划类型、默认 profile、fork 约束与 FORK_CONTEXT_NOTICE |
| `packages/agent-core-v2/src/session/subagent/runAgentTurn.ts` | 驱动子 agent 一轮 loop，提取最后 assistant 文本为 summary |
| `packages/agent-core-v2/src/session/subagent/configSection.ts` | 超时（2h）、secondary model 池/强制模型解析 |
| `packages/agent-core-v2/src/session/subagent/mirrorAgentRun.ts` | 父侧事件镜像（subagent.spawned/completed/...） |
| `packages/agent-core-v2/src/session/agentLifecycle/agentLifecycleService.ts` | agent scope 创建（独立 wire/homedir）、fork（历史拷贝） |
| `packages/agent-core-v2/src/session/agentLifecycle/profile/profiles.ts` | 内置 profile（agent/coder/explore）：工具白名单 + 角色提示词 |
| `packages/agent-core-v2/src/session/agentLifecycle/profile/explore-overlay.md` | explore 只读约束 overlay |
| `packages/agent-core-v2/src/app/agentProfileCatalog/system.md` | 系统提示词模板 |
| `packages/agent-core-v2/src/app/agentProfileCatalog/profile-shared.ts` | TASK_AGENT_ROLE_PREFIX、allowlist / 防递归过滤、渲染函数 |
| `packages/agent-core-v2/src/features/swarm/tools/agent-swarm/agentSwarmTool.ts` | `AgentSwarm` 工具实现与结果 XML 渲染 |
| `packages/agent-core-v2/src/features/swarm/tools/agent-swarm/agent-swarm.ts`（+ `agent-swarm.md`） | Swarm 输入 schema（{{item}} 模板、128 上限）与描述 |
| `packages/agent-core-v2/src/features/swarm/session/agentRunBatch.ts` | 批量并发调度队列（节流、限流重试、并发上限） |
| `packages/agent-core-v2/src/features/swarm/session/sessionSwarmService.ts` | swarm 会话服务：launcher 装配、AgentRunBatch 启动 |
| `packages/agent-core-v2/src/features/swarm/configSection.ts` | swarm 超时配置 |
| `packages/agent-core-v2/src/agent/task/taskService.ts` | 任务管理：前后台、超时、输出持久化、合成 user 通知 |
| `packages/agent-core-v2/src/agent/task/configSection.ts` | maxRunningTasks 等后台任务配置 |
| `packages/agent-core-v2/src/agent/task/notificationXml.ts` | `<notification>` XML 渲染 |
| `packages/agent-core-v2/src/agent/tools/task/{task-list,task-output,task-stop,task-wait}` | TaskList/TaskOutput/TaskStop/WaitFor 管理工具 |
| `packages/agent-core-v2/src/features/tower/tools/spawn/spawnTool.ts`（+ `spawn.md`） | `TowerSpawn`：worktree 隔离的 worker/reviewer 子 agent |
| `packages/agent-core-v2/src/features/tower/tower.ts` | TOWER_WORKER_PROFILE 等 tower 常量 |
| `packages/node-sdk/src/task.ts` | SDK 类型 re-export（SubagentTaskInfo） |
