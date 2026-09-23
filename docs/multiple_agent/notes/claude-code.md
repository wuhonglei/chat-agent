# Claude Code 多 Agent / 子 Agent（subagent）实现方案分析

> 分析对象：`/Users/apple/Desktop/code/claude-code`（Anthropic Claude Code 经 npm sourcemap 泄露的源码备份，见 `README.md:1` "Claude Code's Entire Source Code Got Leaked via a Sourcemap in npm"）。
> **证据性质说明**：该仓库为**逆向/泄露源码**，`docs/` 目录下仅有一篇与多 agent 无关的 `image-compression-scheme.md`（已用 find 确认），因此本文全部证据均为**源码证据**，不存在官方文档描述。
> 核心实现集中在 `src/tools/AgentTool/`（工具本体）、`src/tools/AgentTool/built-in/`（内置 agent 系统提示词）、`src/tools/shared/spawnMultiAgent.ts`（团队 teammate）、`src/tasks/LocalAgentTask/`（后台任务与通知）。

---

## 1. 创建子 agent 的时机

### 结论
- **纯工具调用触发，无隐式自动拆分**：主 agent（或 teammate/coordinator）显式调用 **`Agent` 工具**（旧名 **`Task`**，保留为 alias 兼容）派生子 agent；是否派生由模型根据系统提示里的使用指南自行判断。唯一的"隐式"路径是实验特性 **fork**：`FORK_SUBAGENT` 开启时省略 `subagent_type` 即隐式 fork 出一个继承父上下文的 worker。
- 另有多 agent 团队（Agent Teams / swarm）路径：传 `name` + `team_name` 时走 `spawnTeammate()`（tmux 或 in-process teammate），返回 `teammate_spawned`。
- 部分场景会**强制建议**派生：如 verification agent 完成 3+ 文件改动后必须派生验证 agent（系统提示级约束，非框架强制）。

### 证据
- `/Users/apple/Desktop/code/claude-code/src/tools/AgentTool/constants.ts:1-3`
  ```ts
  export const AGENT_TOOL_NAME = 'Agent'
  // Legacy wire name for backward compat (permission rules, hooks, resumed sessions)
  export const LEGACY_AGENT_TOOL_NAME = 'Task'
  ```
- `/Users/apple/Desktop/code/claude-code/src/tools/AgentTool/AgentTool.tsx:226-228`（工具注册入口 `AgentTool.call()` 即派生入口）
  ```ts
  name: AGENT_TOOL_NAME,
  searchHint: 'delegate work to a subagent',
  aliases: [LEGACY_AGENT_TOOL_NAME],
  ```
- `/Users/apple/Desktop/code/claude-code/src/tools/AgentTool/forkSubagent.ts:22-27`（隐式 fork 触发条件）
  ```
  * - `subagent_type` becomes optional on the Agent tool schema
  * - Omitting `subagent_type` triggers an implicit fork: the child inherits
  *   the parent's full conversation context and system prompt
  ```
- `/Users/apple/Desktop/code/claude-code/src/tools/AgentTool/AgentTool.tsx:284-300`（teammate 派生分支：`if (teamName && name) { ... spawnTeammate({...}) }`）
- `/Users/apple/Desktop/code/claude-code/src/constants/prompts.ts:316-319`（主系统提示中指导何时派生）
  ```
  Use the Agent tool with specialized agents when the task at hand matches the agent's description. Subagents are valuable for parallelizing independent queries or for protecting the main context window from excessive results...
  ```
- `/Users/apple/Desktop/code/claude-code/src/tools/TodoWriteTool/TodoWriteTool.ts:107`（强制建议派生验证 agent 的注入提示）
  ```
  ...Before writing your final summary, spawn the verification agent (subagent_type="${VERIFICATION_AGENT_TYPE}")...
  ```

---

## 2. 子 agent 的上下文管理

### 结论
- **默认全新上下文（零继承对话）**：非 fork 路径下子 agent 的消息列表只有一条 user 消息（即 `prompt`），**不继承父对话历史、父系统提示**；工具描述明确要求父 agent 把背景写进 prompt（"it hasn't seen this conversation"）。
- **继承的全局上下文**：userContext（CLAUDE.md 层级 + 日期）与 systemContext（git status 快照）通过 memoize 的 `getUserContext()/getSystemContext()` 与父共享同源数据；工作目录默认继承当前 cwd（可用 `cwd` 参数或 `isolation:"worktree"` 改写）；可选 `memory: user|project|local` 的 agent 持久记忆会拼进子 agent 系统提示。readFileState（文件读取缓存）非 fork 时新建空缓存，fork 时克隆父缓存。
- **fork 路径完全继承**：父完整对话消息 + 父已渲染系统提示（byte-identical 以共享 prompt cache）。
- **结果回传**：`finalizeAgentTool()` 提取子 agent **最后一条 assistant 消息的 text 内容块原样返回**（不摘要；若最后一条是纯 tool_use 则向前找最近含 text 的 assistant 消息），包成 tool_result 返回父 agent；工具层设 100K 字符上限。空结果显式标注 `(Subagent completed but returned no output.)`，尾部附加 agentId（可用 SendMessage 续接）与 usage 统计。异步 agent 结果通过 `<task-notification>` 注入（见第 6 点）。

### 证据
- `/Users/apple/Desktop/code/claude-code/src/tools/AgentTool/AgentTool.tsx:538-540`（非 fork：单条 user 消息 = 全部输入）
  ```ts
  promptMessages = [createUserMessage({
    content: prompt
  })];
  ```
- `/Users/apple/Desktop/code/claude-code/src/tools/AgentTool/prompt.ts:103`
  ```
  When spawning a fresh agent (with a `subagent_type`), it starts with zero context. Brief the agent like a smart colleague who just walked into the room — it hasn't seen this conversation...
  ```
- `/Users/apple/Desktop/code/claude-code/src/tools/AgentTool/runAgent.ts:370-383`（fork 才传父消息；userContext/systemContext 与父同源）
  ```ts
  const contextMessages: Message[] = forkContextMessages
    ? filterIncompleteToolCalls(forkContextMessages)
    : []
  const initialMessages: Message[] = [...contextMessages, ...promptMessages]
  const agentReadFileState =
    forkContextMessages !== undefined
      ? cloneFileStateCache(toolUseContext.readFileState)
      : createFileStateCacheWithSizeLimit(READ_FILE_STATE_CACHE_SIZE)
  const [baseUserContext, baseSystemContext] = await Promise.all([
    override?.userContext ?? getUserContext(),
    override?.systemContext ?? getSystemContext(),
  ])
  ```
- `/Users/apple/Desktop/code/claude-code/src/tools/AgentTool/runAgent.ts:385-410`（瘦身：Explore/Plan 去掉 claudeMd 与 gitStatus）
  ```
  // Read-only agents (Explore, Plan) don't act on commit/PR/lint rules from CLAUDE.md ...
  const shouldOmitClaudeMd = agentDefinition.omitClaudeMd && ...
  ```
- `/Users/apple/Desktop/code/claude-code/src/context.ts:155-188`（getUserContext = CLAUDE.md + 日期）、`context.ts:116-149`（getSystemContext = gitStatus 快照）
- `/Users/apple/Desktop/code/claude-code/src/tools/AgentTool/AgentTool.tsx:483-512`（fork：继承父系统提示，`forkParentSystemPrompt = toolUseContext.renderedSystemPrompt`）
- `/Users/apple/Desktop/code/claude-code/src/tools/AgentTool/agentToolUtils.ts:297-317`（结果提取 = 最后 assistant 消息 text 块原样）
  ```ts
  let content = lastAssistantMessage.message.content.filter(_ => _.type === 'text')
  if (content.length === 0) { /* 向前找最近含 text 的 assistant 消息 */ }
  ```
- `/Users/apple/Desktop/code/claude-code/src/tools/AgentTool/AgentTool.tsx:229`（截断上限）`maxResultSizeChars: 100_000,`
- `/Users/apple/Desktop/code/claude-code/src/tools/AgentTool/AgentTool.tsx:1347-1350, 1363-1373`（空结果标记 + agentId/usage 尾注）
  ```
  text: '(Subagent completed but returned no output.)'
  ...
  text: `agentId: ${data.agentId} (use SendMessage with to: '${data.agentId}' to continue this agent)...\n<usage>total_tokens: ...`
  ```
- `/Users/apple/Desktop/code/claude-code/src/tools/AgentTool/loadAgentsDir.ts:481-488`（记忆拼入系统提示：`systemPrompt + '\n\n' + loadAgentMemoryPrompt(name, parsed.memory)`）；`agentMemory.ts:12-13`（`'user' (~/.claude/agent-memory/), 'project' (.claude/agent-memory/), or 'local' (.claude/agent-memory-local/)`）
- `/Users/apple/Desktop/code/claude-code/src/tools/AgentTool/forkSubagent.ts:96-105`（fork 上下文构建：`[...history, assistant(all_tool_uses), user(placeholder_results..., directive)]`）
- 工作目录：`AgentTool.tsx:99-100`（`cwd: z.string().optional().describe('Absolute path to run the agent in...')`）、`AgentTool.tsx:590-593`（`isolation === 'worktree'` → `createAgentWorktree(slug)`）

---

## 3. 子 agent 的输入输出内容

### 结论
- **输入 payload**（Agent 工具入参，Zod schema）：`description`（3-5 词短描述）、`prompt`（任务全文，唯一任务输入）、`subagent_type?`（agent 类型，省略时默认 general-purpose 或 fork）、`model?`（`'sonnet'|'opus'|'haiku'`，覆盖 agent 定义的 model，否则继承父）、`run_in_background?`；多 agent 扩展字段 `name?`、`team_name?`、`mode?`（权限模式）、`isolation?`（`'worktree'`，ant 内部另有 `'remote'`）、`cwd?`。
- **输出**是结构化 union：同步完成为 `{status:'completed', prompt, agentId, agentType?, content:[{type:'text',text}], totalToolUseCount, totalDurationMs, totalTokens, usage:{input_tokens, output_tokens, cache_*, server_tool_use, service_tier, cache_creation}}`；异步启动为 `{status:'async_launched', agentId, description, prompt, outputFile, canReadOutputFile?}`；内部另有 `teammate_spawned`、`remote_launched` 两种（不进公开 schema）。`content` 本质是**最终文本报告**（原样 text 块），非中间过程。

### 证据
- `/Users/apple/Desktop/code/claude-code/src/tools/AgentTool/AgentTool.tsx:82-88`（输入 schema）
  ```ts
  const baseInputSchema = lazySchema(() => z.object({
    description: z.string().describe('A short (3-5 word) description of the task'),
    prompt: z.string().describe('The task for the agent to perform'),
    subagent_type: z.string().optional().describe('The type of specialized agent to use for this task'),
    model: z.enum(['sonnet', 'opus', 'haiku']).optional().describe("Optional model override ... If omitted, uses the agent definition's model, or inherits from the parent."),
    run_in_background: z.boolean().optional().describe('Set to true to run this agent in the background. You will be notified when it completes.')
  }));
  ```
- `/Users/apple/Desktop/code/claude-code/src/tools/AgentTool/AgentTool.tsx:93-101`（多 agent + isolation + cwd 字段）
  ```ts
  name: z.string().optional().describe('Name for the spawned agent. Makes it addressable via SendMessage({to: name}) while running.'),
  team_name: ..., mode: ...,
  isolation: z.enum(['worktree'])..., cwd: z.string().optional().describe('Absolute path to run the agent in...'),
  ```
- `/Users/apple/Desktop/code/claude-code/src/tools/AgentTool/agentToolUtils.ts:227-258`（结果 schema）
  ```ts
  z.object({
    agentId: z.string(),
    agentType: z.string().optional(),
    content: z.array(z.object({ type: z.literal('text'), text: z.string() })),
    totalToolUseCount: z.number(), totalDurationMs: z.number(), totalTokens: z.number(),
    usage: z.object({ input_tokens, output_tokens, cache_creation_input_tokens, cache_read_input_tokens, server_tool_use, service_tier, cache_creation }),
  })
  ```
- `/Users/apple/Desktop/code/claude-code/src/tools/AgentTool/AgentTool.tsx:141-155`（输出 union：`syncOutputSchema`（completed + prompt）与 `asyncOutputSchema`（`status: 'async_launched'` 含 `outputFile`））
- `/Users/apple/Desktop/code/claude-code/src/tools/AgentTool/AgentTool.tsx:161-191`（内部 `teammate_spawned` / `remote_launched` 输出类型）

---

## 4. 子 agent 的系统提示词

### 结论
- **内置 agent 的系统提示词是 TS 字符串常量**，位于 `src/tools/AgentTool/built-in/` 各文件（`getSystemPrompt()` 动态生成）；兜底提示是 `DEFAULT_AGENT_PROMPT`（`src/constants/prompts.ts:758`）。运行时经 `enhanceSystemPromptWithEnvDetails()` 追加环境信息（绝对路径、emoji 规范等）。
- **自定义 agent（`.claude/agents/*.md`）：markdown 正文即系统提示词**，frontmatter 提供元数据（`name`、`description`、`tools`、`disallowedTools`、`model`、`permissionMode`、`maxTurns`、`memory`、`mcpServers`、`hooks`、`skills`、`background`、`isolation` 等）；加载来源为 managed（策略）→ 用户 `~/.claude/agents/` → 项目 `.claude/agents/`（含沿目录向上收集）。
- 核心内容共性：角色定位 + 硬约束（只读 agent 的 READ-ONLY 禁令）+ 工具使用指南 + 输出格式要求。fork worker 另有一段固定"boilerplate"指令（`buildChildMessage`）："You are a forked worker process. You are NOT the main agent."，规定禁止再派生、禁止闲聊、以 `Scope:/Result:/Key files:` 结构汇报。

### 证据
- `/Users/apple/Desktop/code/claude-code/src/constants/prompts.ts:758`（兜底 DEFAULT_AGENT_PROMPT）
  ```
  You are an agent for Claude Code, Anthropic's official CLI for Claude. Given the user's message, you should use the tools available to complete the task. Complete the task fully—don't gold-plate, but don't leave it half-done. When you complete the task, respond with a concise report ... the caller will relay this to the user ...
  ```
- `/Users/apple/Desktop/code/claude-code/src/tools/AgentTool/built-in/generalPurposeAgent.ts:3-23`（general-purpose 提示，`tools: ['*']`）
  ```
  const SHARED_PREFIX = `You are an agent for Claude Code ... Complete the task fully—don't gold-plate, but don't leave it half-done.`
  ...When you complete the task, respond with a concise report covering what was done and any key findings — the caller will relay this to the user...
  ```
- `/Users/apple/Desktop/code/claude-code/src/tools/AgentTool/built-in/exploreAgent.ts:24-56`（Explore：只读搜索专家）
  ```
  You are a file search specialist for Claude Code ...
  === CRITICAL: READ-ONLY MODE - NO FILE MODIFICATIONS ===
  ...You are meant to be a fast agent that returns output as quickly as possible...
  ```
- `/Users/apple/Desktop/code/claude-code/src/tools/AgentTool/built-in/planAgent.ts:21-70`（Plan：`You are a software architect and planning specialist ...`，要求输出 `### Critical Files for Implementation` 3-5 个文件）
- `/Users/apple/Desktop/code/claude-code/src/tools/AgentTool/built-in/verificationAgent.ts:10-129`（verification：对抗式验证，要求 `Command run / Output observed / Result` 格式并以 `VERDICT: PASS|FAIL|PARTIAL` 收尾；`:150-151` 有 `criticalSystemReminder_EXPERIMENTAL` 每轮重注入）
- `/Users/apple/Desktop/code/claude-code/src/tools/AgentTool/built-in/claudeCodeGuideAgent.ts:30-38`（claude-code-guide：Claude Code / Agent SDK / API 文档问答）
- `/Users/apple/Desktop/code/claude-code/src/tools/AgentTool/loadAgentsDir.ts:713-732`（`.claude/agents/*.md` 正文即系统提示）
  ```ts
  const systemPrompt = content.trim()
  ...
  getSystemPrompt: () => {
    if (isAutoMemoryEnabled() && memory) {
      const memoryPrompt = loadAgentMemoryPrompt(agentType, memory)
      return systemPrompt + '\n\n' + memoryPrompt
    }
    return systemPrompt
  },
  ```
- `/Users/apple/Desktop/code/claude-code/src/utils/markdownConfigLoader.ts:297-305`（加载路径：managed / user(`getClaudeConfigHomeDir()/agents` = `~/.claude/agents`) / project(`.claude/agents`)）
  ```ts
  const userDir = join(getClaudeConfigHomeDir(), subdir)
  const managedDir = join(getManagedFilePath(), '.claude', subdir)
  const projectDirs = getProjectDirsUpToHome(subdir, cwd)
  ```
- `/Users/apple/Desktop/code/claude-code/src/tools/AgentTool/loadAgentsDir.ts:541-560`（frontmatter 必填 `name` + `description`；`:106-133` BaseAgentDefinition 全字段注释）
- `/Users/apple/Desktop/code/claude-code/src/tools/AgentTool/forkSubagent.ts:171-198`（fork worker 固定指令）
  ```
  You are a forked worker process. You are NOT the main agent.
  RULES (non-negotiable):
  1. ... You ARE the fork. Do NOT spawn sub-agents; execute directly.
  ...
  9. Your response MUST begin with "Scope:"...
  ```
- `/Users/apple/Desktop/code/claude-code/src/tools/AgentTool/runAgent.ts:906-932`（`getAgentSystemPrompt()`：agent 提示 + `enhanceSystemPromptWithEnvDetails`，异常时回退 DEFAULT_AGENT_PROMPT）

---

## 5. 子 agent 的工具范围

### 结论
- **白名单 + 黑名单裁剪**，不简单继承父级：worker 工具池用 `assembleToolPool(workerPermissionContext, ...)` **独立重建**（不受父工具限制影响），再经 `resolveAgentTools()` 按 agent 定义的 `tools`（白名单，支持 `'*'` 通配）与 `disallowedTools`（黑名单）过滤；两者都有时白名单先被黑名单剔除。
- **全局禁止集**：所有子 agent 都拿不到 `TaskOutput`、`ExitPlanMode`、`EnterPlanMode`、`AskUserQuestion`、`TaskStop`；**默认也拿不到 `Agent` 工具本身（防递归）**，仅 Anthropic 内部构建（`USER_TYPE === 'ant'`）放开嵌套。后台（async）agent 另有更窄的白名单（读文件/搜索/读写文件/shell/Skill 等），MCP 工具对所有 agent 放行。
- **深度限制**：默认**深度为 1**（子 agent 无 Agent 工具，硬性禁止再派生）；ant 内部可嵌套但无显式深度上限（仅 `queryTracking.depth` 递增计数）；fork 子孙在调用时点被显式拒绝再次 fork。权限上父级审批不泄漏：`allowedTools` 传入时清空父 session 级 allow rules（保留 SDK `--allowedTools` 的 cliArg 规则）。

### 证据
- `/Users/apple/Desktop/code/claude-code/src/constants/tools.ts:36-46`（全局禁止集）
  ```ts
  export const ALL_AGENT_DISALLOWED_TOOLS = new Set([
    TASK_OUTPUT_TOOL_NAME,
    EXIT_PLAN_MODE_V2_TOOL_NAME,
    ENTER_PLAN_MODE_TOOL_NAME,
    // Allow Agent tool for agents when user is ant (enables nested agents)
    ...(process.env.USER_TYPE === 'ant' ? [] : [AGENT_TOOL_NAME]),
    ASK_USER_QUESTION_TOOL_NAME,
    TASK_STOP_TOOL_NAME,
    ...
  ])
  ```
- `/Users/apple/Desktop/code/claude-code/src/constants/tools.ts:55-71`（`ASYNC_AGENT_ALLOWED_TOOLS`：后台 agent 白名单：Read/WebSearch/TodoWrite/Grep/WebFetch/Glob/shell/Edit/Write/NotebookEdit/Skill/SyntheticOutput/ToolSearch/worktree）；`:90-92` 注释 `"AgentTool: Blocked to prevent recursion"`
- `/Users/apple/Desktop/code/claude-code/src/tools/AgentTool/agentToolUtils.ts:81-115`（`filterToolsForAgent`：MCP 全放行、禁止集过滤、async 白名单过滤）
- `/Users/apple/Desktop/code/claude-code/src/tools/AgentTool/agentToolUtils.ts:158-173`（白名单/黑名单/通配逻辑）
  ```ts
  const allowedAvailableTools = filteredAvailableTools.filter(tool => !disallowedToolSet.has(tool.name))
  // If tools is undefined or ['*'], allow all tools (after filtering disallowed)
  const hasWildcard = agentTools === undefined || (agentTools.length === 1 && agentTools[0] === '*')
  ```
- `/Users/apple/Desktop/code/claude-code/src/tools/AgentTool/AgentTool.tsx:568-577`（工具池独立重建，不受父限制影响）
  ```
  // Assemble the worker's tool pool independently of the parent's.
  // Workers always get their tools from assembleToolPool with their own
  // permission mode, so they aren't affected by the parent's tool restrictions.
  const workerTools = assembleToolPool(workerPermissionContext, appState.mcp.tools);
  ```
- `/Users/apple/Desktop/code/claude-code/src/tools/AgentTool/AgentTool.tsx:332-334`（fork 递归拒绝）
  ```ts
  throw new Error('Fork is not available inside a forked worker. Complete your task directly using your tools.');
  ```
- `/Users/apple/Desktop/code/claude-code/src/tools/AgentTool/built-in/exploreAgent.ts:67-73`（示例：`disallowedTools: [AGENT_TOOL_NAME, EXIT_PLAN_MODE_TOOL_NAME, FILE_EDIT_TOOL_NAME, FILE_WRITE_TOOL_NAME, NOTEBOOK_EDIT_TOOL_NAME]`）
- `/Users/apple/Desktop/code/claude-code/src/utils/forkedAgent.ts:451-455`（深度仅计数，未发现硬上限）
  ```ts
  queryTracking: {
    chainId: randomUUID(),
    depth: (parentContext.queryTracking?.depth ?? -1) + 1,
  },
  ```
- `/Users/apple/Desktop/code/claude-code/src/tools/AgentTool/runAgent.ts:465-479`（权限隔离：`Only clear session-level rules from the parent to prevent unintended leakage`，保留 `cliArg`）
- `/Users/apple/Desktop/code/claude-code/src/tools/AgentTool/prompt.ts:15-37`（工具范围如何展示给父模型：`All tools except X, Y, Z` / `None` / 具体列表）
- **未找到**：除 ant 嵌套放开外的显式"最大嵌套深度"数字限制（如 depth<N 校验）——不存在。

---

## 6. 子 agent 的运行方式

### 结论
- **同步阻塞是默认**：前台运行会占住父 turn 直到完成；但可 `run_in_background: true`（或 agent 定义 `background: true`）转异步后台，**同步任务也可随时手动/自动转后台**（跑满 120s 自动后台，可配）；fork 实验开启时强制全部异步。
- **并发**：`Agent` 工具 `isConcurrencySafe() = true`，鼓励一条消息多个 Agent 调用并行；框架级并发上限是通用工具并发 `CLAUDE_CODE_MAX_TOOL_USE_CONCURRENCY`（默认 10）。**未找到专门的子 agent 数量上限**。
- **超时**：**未找到基于时间的子 agent 超时**；轮次上限 `maxTurns`（agent frontmatter 可配，超限发 `max_turns_reached` 终止）；`TaskOutput` 主动等待有超时参数（默认 30s，最大 600s）。
- **结果通知回父**：同步 = 工具调用直接返回 tool_result；异步 = 完成时由 `enqueueAgentNotification()` 生成 `<task-notification>` XML（含 task_id、output_file、status、summary、`<result>`、`<usage>`），以**user-role 排队消息**注入父对话的下一轮；父也可用 `TaskOutput(task_id, block=true)` 阻塞获取、`SendMessage(to: agentId)` 续接（保留完整上下文）、`TaskStop` 终止（杀死时回传部分结果）。

### 证据
- `/Users/apple/Desktop/code/claude-code/src/tools/AgentTool/AgentTool.tsx:555-567`（异步判定）
  ```ts
  const forceAsync = isForkSubagentEnabled();
  ...
  const shouldRunAsync = (run_in_background === true || selectedAgent.background === true || isCoordinator || forceAsync || assistantForceAsync || ...) && !isBackgroundTasksDisabled;
  ```
- `/Users/apple/Desktop/code/claude-code/src/tools/AgentTool/AgentTool.tsx:70-77`（120s 自动后台）
  ```ts
  // Auto-background agent tasks after this many ms (0 = disabled)
  function getAutoBackgroundMs(): number {
    if (isEnvTruthy(process.env.CLAUDE_AUTO_BACKGROUND_TASKS) || getFeatureValue_CACHED_MAY_BE_STALE('tengu_auto_background_agents', false)) {
      return 120_000;
    }
    return 0;
  }
  ```
- `/Users/apple/Desktop/code/claude-code/src/tools/AgentTool/AgentTool.tsx:886-892`（同步循环 `Promise.race([nextMessagePromise, backgroundPromise])` —— 同步可中途转后台并立即返回 `async_launched`，`:1041-1051`）
- `/Users/apple/Desktop/code/claude-code/src/tools/AgentTool/AgentTool.tsx:1273-1275`（`isConcurrencySafe() { return true; }`）
- `/Users/apple/Desktop/code/claude-code/src/services/tools/toolOrchestration.ts:8-12`（并发上限）
  ```ts
  function getMaxToolUseConcurrency(): number {
    return parseInt(process.env.CLAUDE_CODE_MAX_TOOL_USE_CONCURRENCY || '', 10) || 10
  }
  ```
- `/Users/apple/Desktop/code/claude-code/src/tools/AgentTool/prompt.ts:271`（并行指引：`you MUST send a single message with multiple Agent tool use content blocks`）
- `/Users/apple/Desktop/code/claude-code/src/tools/AgentTool/runAgent.ts:748-757`（`maxTurns: maxTurns ?? agentDefinition.maxTurns` 传入 query）、`/Users/apple/Desktop/code/claude-code/src/query.ts:1506-1508`（`if (maxTurns && nextTurnCountOnAbort > maxTurns)`）、`runAgent.ts:773-787`（`max_turns_reached` → break）
- `/Users/apple/Desktop/code/claude-code/src/tools/TaskOutputTool/TaskOutputTool.tsx:30-34`（主动等待）
  ```ts
  task_id: z.string().describe('The task ID to get output from'),
  block: semanticBoolean(z.boolean().default(true)).describe('Whether to wait for completion'),
  timeout: z.number().min(0).max(600000).default(30000).describe('Max wait time in ms')
  ```
- `/Users/apple/Desktop/code/claude-code/src/tasks/LocalAgentTask/LocalAgentTask.tsx:246-261`（异步完成通知格式与注入方式）
  ```ts
  const message = `<${TASK_NOTIFICATION_TAG}>
  <${TASK_ID_TAG}>${taskId}</${TASK_ID_TAG}>${toolUseIdLine}
  <${OUTPUT_FILE_TAG}>${outputPath}</${OUTPUT_FILE_TAG}>
  <${STATUS_TAG}>${status}</${STATUS_TAG}>
  <${SUMMARY_TAG}>${summary}</${SUMMARY_TAG}>${resultSection}${usageSection}${worktreeSection}
  </${TASK_NOTIFICATION_TAG}>`;
  enqueuePendingNotification({ value: message, mode: 'task-notification' });
  ```
- `/Users/apple/Desktop/code/claude-code/src/coordinator/coordinatorMode.ts:144`（通知以 user-role 消息到达：`Worker results arrive as **user-role messages** containing <task-notification> XML. They look like user messages but are not.`）
- `/Users/apple/Desktop/code/claude-code/src/tools/AgentTool/AgentTool.tsx:686-698`（后台 agent 使用独立 AbortController，不随父 ESC 取消：`Don't link to parent's abort controller -- background agents should survive when the user presses ESC`）
- `/Users/apple/Desktop/code/claude-code/src/tools/AgentTool/agentToolUtils.ts:488-500`（被 kill 时 `extractPartialResult` 回传部分结果）
- `/Users/apple/Desktop/code/claude-code/src/tools/TaskStopTool/prompt.ts:1-8`（`TaskStop`：`Stops a running background task by its ID`）
- `/Users/apple/Desktop/code/claude-code/src/tools/AgentTool/prompt.ts:267`（续接语义：`To continue a previously spawned agent, use SendMessage with the agent's ID or name as the 'to' field. The agent resumes with its full context preserved.`；实现于 `src/tools/AgentTool/resumeAgent.ts`）
- **未找到**：子 agent 墙钟超时（timeout）配置——仅有 maxTurns、TaskOutput 等待超时、以及 MCP pending 等待 30s（`AgentTool.tsx:378`）。

---

## 关键源码文件清单

| 文件 | 作用 |
|---|---|
| `src/tools/AgentTool/AgentTool.tsx` | Agent（旧 Task）工具主体：输入/输出 schema、spawn 分支（teammate/fork/remote/同步/异步）、结果序列化 |
| `src/tools/AgentTool/constants.ts` | 工具名 `Agent`/`Task`、一次性内置 agent 集合 |
| `src/tools/AgentTool/prompt.ts` | Agent 工具面向父模型的使用说明（何时用/何时不用/如何写 prompt/fork 指南） |
| `src/tools/AgentTool/runAgent.ts` | 子 agent 执行器：上下文组装、系统提示、工具解析、query 循环、sidechain 转录、清理 |
| `src/tools/AgentTool/agentToolUtils.ts` | 工具过滤 `filterToolsForAgent`/`resolveAgentTools`、结果 schema/finalize、后台生命周期、handoff 安全分类 |
| `src/tools/AgentTool/loadAgentsDir.ts` | `.claude/agents/*.md` 与 JSON agent 定义解析（frontmatter → AgentDefinition） |
| `src/tools/AgentTool/forkSubagent.ts` | fork 实验：FORK_AGENT 定义、fork 消息构建、递归防护、fork worker boilerplate 指令 |
| `src/tools/AgentTool/resumeAgent.ts` | SendMessage 续接后台 agent |
| `src/tools/AgentTool/agentMemory.ts` / `agentMemorySnapshot.ts` | agent 持久记忆（user/project/local 作用域） |
| `src/tools/AgentTool/built-in/{generalPurpose,explore,plan,verification,claudeCodeGuide}Agent.ts` + `builtInAgents.ts` | 内置 agent 定义与系统提示词原文 |
| `src/constants/tools.ts` | 子 agent 工具禁止集 / 后台白名单 / coordinator 工具集 |
| `src/constants/prompts.ts` | 主系统提示中的 Agent 使用章节、DEFAULT_AGENT_PROMPT |
| `src/utils/forkedAgent.ts` | `createSubagentContext`（子 agent 上下文隔离）、`runForkedAgent` |
| `src/utils/markdownConfigLoader.ts` | `.claude/agents/` 多来源加载（managed/user/project） |
| `src/tasks/LocalAgentTask/LocalAgentTask.tsx` | 后台 agent 任务注册/进度/kill 与 `<task-notification>` 生成 |
| `src/tools/TaskOutputTool/TaskOutputTool.tsx` | 父 agent 阻塞/非阻塞获取后台结果 |
| `src/tools/TaskStopTool/` | 终止后台 agent |
| `src/tools/shared/spawnMultiAgent.ts` | Agent Teams teammate 派生（tmux/in-process） |
| `src/services/tools/toolOrchestration.ts` | 工具并发上限（子 agent 并行的实际上限） |
| `src/context.ts` | getUserContext（CLAUDE.md）/ getSystemContext（gitStatus）——子 agent 共享的全局上下文 |
