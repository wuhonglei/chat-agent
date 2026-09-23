# 多 Agent（子 agent）实现方案对比：ZCode / kimi-code / codex / hermes-agent / claude-code

> 对比维度：① 创建子 agent 的时机 ② 子 agent 上下文管理 ③ 输入输出内容 ④ 系统提示词 ⑤ 工具范围 ⑥ 运行方式（同步/异步）
> 证据均为源码 path:line（行号以 2026-09-22 代码为准）。逐框架完整分析（含代码摘录与全部文件清单）见 `notes/` 目录：
> `/Users/apple/Desktop/code/chat-agent/docs/multiple_agent/notes/{zcode,kimi-code,codex,hermes-agent,claude-code}.md`
> 证据性质：claude-code 仓库为 npm sourcemap 泄露源码（无官方多 agent 文档，全部为源码证据）；其余四家为完整开源仓库。

---

## 0. 一句话画像

| 框架 | 语言 | 子 agent 入口 | 一句话画像 |
|---|---|---|---|
| ZCode | TS | `Agent`（别名 `Task`）+ `CreateWorkflow` | 零上下文一次性子运行时 + profile 白名单，深度硬限 1 层，另有脚本化 workflow 第二路径 |
| kimi-code | TS | `Agent` / `AgentSwarm` / `TowerSpawn` | 零上下文（可实验性 fork）同进程子 loop，profile 白名单，swarm 批量扇出 128 |
| codex | Rust | `spawn_agent`（+`wait_agent` 等协作工具族） | 真正的多 agent 团队：子=完整线程，邮箱消息通信，默认带历史 fork，全工具继承，可递归（V2） |
| hermes-agent | Python | `delegate_task`（spawn/批量/控制面三合一） | 顶层强制异步的批量委派，继承父工具集做减法，摘要制回传 + JSON Schema 输出契约 |
| claude-code | TS | `Agent`（旧名 `Task`） | 零上下文 worker（实验性 fork/teammate），工具池独立重建 + 白名单/黑名单，默认禁递归 |

<div class="diagram"><svg viewBox="0 0 820 660" style="width:100%;max-width:820px;height:auto;" fill="none">
<defs><marker id="arr1" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6 z" fill="#64748b"/></marker><marker id="arr1p" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6 z" fill="#7c3aed"/></marker></defs>
<rect x="330" y="14" width="160" height="40" rx="20" fill="#f1f5f9" stroke="#64748b" stroke-width="2"/>
<text x="410" y="39" font-family="Noto Sans SC, sans-serif" font-size="13" font-weight="600" fill="#334155" text-anchor="middle">用户任务输入</text>
<line x1="410" y1="54" x2="410" y2="84" stroke="#64748b" stroke-width="2" marker-end="url(#arr1)"/>
<rect x="40" y="88" width="740" height="150" rx="16" fill="#eff6ff" stroke="#2563eb" stroke-width="2"/>
<text x="58" y="112" font-family="Noto Sans SC, sans-serif" font-size="12.5" font-weight="600" fill="#1d4ed8">父 Agent（模型决策：是否 / 如何派生）</text>
<rect x="80" y="128" width="200" height="44" rx="22" fill="#fef3c7" stroke="#d97706" stroke-width="2"/>
<text x="180" y="155" font-family="Noto Sans SC, sans-serif" font-size="12.5" font-weight="600" fill="#92400e" text-anchor="middle">派生决策（工具调用）</text>
<line x1="282" y1="150" x2="316" y2="150" stroke="#64748b" stroke-width="2" marker-end="url(#arr1)"/>
<rect x="320" y="128" width="160" height="44" rx="22" fill="#fee2e2" stroke="#dc2626" stroke-width="2"/>
<text x="400" y="155" font-family="Noto Sans SC, sans-serif" font-size="12.5" font-weight="600" fill="#991b1b" text-anchor="middle">闸门校验</text>
<line x1="482" y1="150" x2="516" y2="150" stroke="#64748b" stroke-width="2" marker-end="url(#arr1)"/>
<rect x="520" y="128" width="220" height="44" rx="22" fill="#ede9fe" stroke="#7c3aed" stroke-width="2"/>
<text x="630" y="155" font-family="Noto Sans SC, sans-serif" font-size="12.5" font-weight="600" fill="#5b21b6" text-anchor="middle">构建子任务输入</text>
<text x="70" y="218" font-family="Noto Sans SC, sans-serif" font-size="10" fill="#64748b">入口工具：ZCode / claude-code「Agent(Task)」· kimi「Agent / AgentSwarm / TowerSpawn」· codex「spawn_agent」· hermes「delegate_task」</text>
<line x1="630" y1="174" x2="630" y2="284" stroke="#64748b" stroke-width="2" marker-end="url(#arr1)"/>
<rect x="40" y="288" width="740" height="190" rx="16" fill="#ecfdf5" stroke="#059669" stroke-width="2"/>
<text x="58" y="312" font-family="Noto Sans SC, sans-serif" font-size="12.5" font-weight="600" fill="#065f46">子 Agent 运行时（独立会话 / 线程 / 上下文）</text>
<rect x="70" y="330" width="210" height="40" rx="20" fill="#d1fae5" stroke="#059669" stroke-width="2"/>
<text x="175" y="355" font-family="Noto Sans SC, sans-serif" font-size="12" font-weight="600" fill="#065f46" text-anchor="middle">上下文注入（零继承/fork）</text>
<rect x="310" y="330" width="190" height="40" rx="20" fill="#d1fae5" stroke="#059669" stroke-width="2"/>
<text x="405" y="355" font-family="Noto Sans SC, sans-serif" font-size="12" font-weight="600" fill="#065f46" text-anchor="middle">系统提示（定制/继承）</text>
<rect x="530" y="330" width="220" height="40" rx="20" fill="#d1fae5" stroke="#059669" stroke-width="2"/>
<text x="640" y="355" font-family="Noto Sans SC, sans-serif" font-size="12" font-weight="600" fill="#065f46" text-anchor="middle">工具面（白名单/减法/全继承）</text>
<line x1="175" y1="372" x2="330" y2="406" stroke="#64748b" stroke-width="2" marker-end="url(#arr1)"/>
<line x1="405" y1="372" x2="410" y2="404" stroke="#64748b" stroke-width="2" marker-end="url(#arr1)"/>
<line x1="640" y1="372" x2="492" y2="406" stroke="#64748b" stroke-width="2" marker-end="url(#arr1)"/>
<rect x="280" y="408" width="260" height="44" rx="22" fill="#d1fae5" stroke="#059669" stroke-width="2"/>
<text x="410" y="435" font-family="Noto Sans SC, sans-serif" font-size="12.5" font-weight="600" fill="#065f46" text-anchor="middle">子 agent 工具循环（maxTurns/预算）</text>
<path d="M410 452 L410 486 L265 486 L265 514" stroke="#64748b" stroke-width="2" marker-end="url(#arr1)"/>
<path d="M410 486 L615 486 L615 514" stroke="#64748b" stroke-width="2" marker-end="url(#arr1)"/>
<rect x="120" y="518" width="290" height="44" rx="22" fill="#dbeafe" stroke="#2563eb" stroke-width="2"/>
<text x="265" y="545" font-family="Noto Sans SC, sans-serif" font-size="12.5" font-weight="600" fill="#1d4ed8" text-anchor="middle">同步：tool_result（原文/摘要裁剪）</text>
<rect x="470" y="518" width="290" height="44" rx="22" fill="#ede9fe" stroke="#7c3aed" stroke-width="2"/>
<text x="615" y="545" font-family="Noto Sans SC, sans-serif" font-size="12.5" font-weight="600" fill="#5b21b6" text-anchor="middle">异步：通知注入父的下一 turn</text>
<path d="M762 540 L794 540 L794 140 L784 140" stroke="#7c3aed" stroke-width="2" stroke-dasharray="6 4" marker-end="url(#arr1p)"/>
<text x="775" y="330" font-family="Noto Sans SC, sans-serif" font-size="10.5" fill="#7c3aed" text-anchor="middle" transform="rotate(-90 775 330)">结果进入父上下文</text>
<line x1="250" y1="620" x2="295" y2="620" stroke="#64748b" stroke-width="2" marker-end="url(#arr1)"/>
<text x="305" y="625" font-family="Noto Sans SC, sans-serif" font-size="11.5" fill="#475569">控制流（同步调用）</text>
<line x1="470" y1="620" x2="515" y2="620" stroke="#7c3aed" stroke-width="2" stroke-dasharray="6 4" marker-end="url(#arr1p)"/>
<text x="525" y="625" font-family="Noto Sans SC, sans-serif" font-size="11.5" fill="#475569">异步通知 / 反馈回传</text>
</svg></div>
<p class="diagram-caption">图 1：子 agent 通用生命周期架构（五框架共享骨架：派生决策 → 闸门 → 构造三要素 → 运行 → 回传/通知）</p>

---

## 1. 总览矩阵

| 维度 | ZCode | kimi-code | codex | hermes-agent | claude-code |
|---|---|---|---|---|---|
| ① 创建时机 | 模型调 `Agent`/`Task` 工具；workflow 走 `CreateWorkflow`；`SendMessage` 续跑 | 模型调 `Agent`/`AgentSwarm`/`TowerSpawn`；`Agent(resume)` 续跑 | 模型调 `spawn_agent`（MultiAgentMode 门控：默认 ExplicitRequestOnly，Ultra 档 Proactive）；内部 4 类隐式派生（review/guardian/compact/记忆合并） | 模型调 `delegate_task`；另有 `/review`、插件 API 两个非模型入口；cron 不派生 | 模型调 `Agent`/`Task`；fork 实验省略 `subagent_type` 隐式 fork；`name+team_name` 走 teammate |
| ② 上下文 | 全新会话（`subagent_<agentId>`），零历史；继承 cwd/env/AGENTS.md/模型/MCP 快照/Skill | 默认零历史；实验 `fork:true` 拷父全历史+免责注记；继承权限模式/用户工具/cwd/模型 | **默认 `fork_turns=all` 带全历史**（可 `N`/`none`）；继承 base+developer 指令/cwd/审批沙箱快照/MCP/skills | 全新会话，零历史；`skip_memory`/`skip_context_files`，但补注入工作区 AGENTS.md（跳过 SOUL.md）；可选 worktree | 默认零历史（仅 1 条 user prompt）；fork 实验继承全历史+父系统提示（byte-identical）；共享 CLAUDE.md/gitStatus |
| ② 结果回传 | 最后 assistant 文本**原样**，120KB 上限（artifact+head 预览） | 最后 assistant 文本**原样**（summary） | 最终消息**原样**（FINAL_ANSWER），仅错误文本截 ~900 token | **摘要制**：final_response 按预算裁剪（默认 24000 字符，超限 75%头+25%尾+spill 文件+read_file 指针） | 最后 assistant text 块**原样**，100K 字符上限 |
| ③ 输入 | `description`/`prompt`/`subagent_type`/`run_in_background`（刻意不暴露 model，无附件） | +`resume`/`fork`/`model`；Swarm 有 `prompt_template`+`items[]`；无附件 | `message`/`task_name`/`agent_type`/`model`/`reasoning_effort`/`fork_turns`；V1 有 `items` 结构化附件（text/image_url/path…） | `tasks=[{goal,context,output_schema,images≤8,group}]` + `action/subagent_id/message` 控制面 | `description`/`prompt`/`subagent_type`/`model`/`run_in_background` + `name/team_name/mode/isolation/cwd` |
| ③ 输出 | 结构化 `AgentCompletedOutput` / `AgentBackgroundedOutput`（含 usage），3 个落盘 artifact | schema `{result,usage}`，父看到格式化文本（agent_id/status/`[summary]`/resume_hint）；Swarm 为 XML | `spawn_agent` 返回 `{task_name,nickname}`；结果本体走 FINAL_ANSWER 消息；`wait_agent` 返回 `{message,timed_out}` | JSON `{results:[entry…]}`（status/summary/tokens/tool_trace/schema_valid…）；后台先给 dispatch handle | 结构化 union：`completed`（content 文本+usage）/ `async_launched`（outputFile）/ teammate_spawned |
| ④ 系统提示词 | 代码模板拼装 4 层（profile 模板+公共 Notes+环境块+可选记忆），自定义 profile=markdown 正文 | 共享模板 `system.md` + `TASK_AGENT_ROLE_PREFIX`（"父只能看到你最后一条消息，勿问最终用户"）+ coder/explore 角色 | **无独立系统提示**：继承父 base instructions；专属提示=developer 角色 usage hint（`<multi_agent_role>`，可配置覆盖）；内部子 agent（review/guardian）整体替换提示 | `ephemeral_system_prompt` 现场拼装："focused subagent"+CONTEXT+WORKSPACE+完成指令；goal 作首条 user 消息；orchestrator 追加派生授权块 | 内置 TS 常量（general-purpose/Explore/Plan/verification/guide）；自定义 `.claude/agents/*.md` 正文即提示；fork worker 固定 boilerplate |
| ⑤ 工具范围 | profile 白名单（general-purpose=`*` 展开父面、Explore=只读 7 工具）；强制禁 plan 工具；**结构性禁递归（深度 1）**；Explore 独立 yolo 权限 | profile 白名单（coder 有写无派生、explore 只读）；`withoutDelegatingTargets` 防递归 → **实际 2 层**；无沙箱差异 | **全工具继承**（"same tools as you"）；V1 深度限 1（`agent_max_depth`），V2 可递归；内部 delegate 禁 Collab 防递归 | 继承父集做减法：禁 `{delegate_task,clarify,memory,send_message,cronjob_manage}` + 剔 delegation/kanban；默认深度 1，orchestrator 按深度拿回 delegate_task | 工具池**独立重建**（不受父限制影响）→ 白名单/黑名单过滤；全局禁 TaskOutput/Plan/AskUserQuestion/TaskStop，**默认禁 Agent（防递归）**，ant 内部可嵌套 |
| ⑥ 运行方式 | 默认同步阻塞；`run_in_background` 异步；可 120s 级 `autoBackgroundMs` 自动转后台 | 默认同步阻塞（waitForForegroundRelease）；`run_in_background` 异步；后台需 Task 管理工具在位 | **spawn 异步非阻塞**（投递 NEW_TASK 即返回）；`wait_agent` 是唯一阻塞点（默认 30s，上限 1h）；邮箱消息通信 | **顶层强制后台异步**；orchestrator 再派生强制同步；无消费者/池满自动降级同步 | 默认同步阻塞；`run_in_background`/`background:true` 异步；120s 自动转后台；fork 开启时强制全异步 |
| ⑥ 并发/超时 | 无专门上限（工具调度 DEFAULT_MAX_CONCURRENCY=10）；600s 空闲看门狗；maxTurns 缺省 4 | Swarm≤128（启动节流 5 个后每 700ms）；后台任务受 maxRunningTasks；超时默认 2h | V2 并发 4 槽（含 root）/ V1 总线程 6；无运行超时（wait 超时 10s~1h） | `max_concurrent_children` 默认 10，池满拒绝不排队；无墙钟超时（心跳陈旧 450s/工具内 1200s 判死） | 无专门上限（工具并发 CLAUDE_CODE_MAX_TOOL_USE_CONCURRENCY=10）；无时间超时（maxTurns + TaskOutput 等 30~600s） |
| ⑥ 结果通知 | 后台完成注入 `<task-notification>` XML（120k 截断）+ 会话事件 | 合成 user 消息 `<notification>` XML 自动入后续 turn | FINAL_ANSWER 以 `trigger_turn=false` 投父邮箱（不打断父 turn）+ SubAgentActivity 事件 | `type="async_delegation"` 事件入 completion_queue，**回合之间**作为新消息回父 | `<task-notification>` XML 以 user-role 排队消息注入下一轮 |

---

## 2. 逐维度深挖

### 2.1 创建子 agent 的时机

<div class="diagram"><svg viewBox="0 0 820 530" style="width:100%;max-width:820px;height:auto;" fill="none">
<defs><marker id="arr2" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6 z" fill="#64748b"/></marker></defs>
<rect x="60" y="30" width="250" height="44" rx="22" fill="#dbeafe" stroke="#2563eb" stroke-width="2"/>
<text x="185" y="58" font-family="Noto Sans SC, sans-serif" font-size="12.5" font-weight="600" fill="#1d4ed8" text-anchor="middle">模型决定派生（显式工具调用）</text>
<line x1="312" y1="52" x2="346" y2="52" stroke="#64748b" stroke-width="2" marker-end="url(#arr2)"/>
<rect x="350" y="30" width="250" height="44" rx="22" fill="#fee2e2" stroke="#dc2626" stroke-width="2"/>
<text x="475" y="58" font-family="Noto Sans SC, sans-serif" font-size="12.5" font-weight="600" fill="#991b1b" text-anchor="middle">闸门：深度 / pause / 配额 / 模式</text>
<line x1="602" y1="52" x2="636" y2="52" stroke="#64748b" stroke-width="2" marker-end="url(#arr2)"/>
<rect x="640" y="30" width="150" height="44" rx="22" fill="#ede9fe" stroke="#7c3aed" stroke-width="2"/>
<text x="715" y="58" font-family="Noto Sans SC, sans-serif" font-size="12.5" font-weight="600" fill="#5b21b6" text-anchor="middle">构建子请求</text>
<path d="M715 74 L715 120 L285 120 L285 166" stroke="#64748b" stroke-width="2" marker-end="url(#arr2)"/>
<path d="M715 120 L615 120 L615 166" stroke="#64748b" stroke-width="2" marker-end="url(#arr2)"/>
<rect x="145" y="170" width="280" height="56" rx="22" fill="#fef3c7" stroke="#d97706" stroke-width="2"/>
<text x="285" y="194" font-family="Noto Sans SC, sans-serif" font-size="12.5" font-weight="600" fill="#92400e" text-anchor="middle">同步阻塞：await 子完成</text>
<text x="285" y="214" font-family="Noto Sans SC, sans-serif" font-size="11.5" fill="#92400e" text-anchor="middle">结果 = tool_result 直接回传</text>
<rect x="475" y="170" width="280" height="56" rx="22" fill="#d1fae5" stroke="#059669" stroke-width="2"/>
<text x="615" y="194" font-family="Noto Sans SC, sans-serif" font-size="12.5" font-weight="600" fill="#065f46" text-anchor="middle">异步后台：立即返回 handle</text>
<text x="615" y="214" font-family="Noto Sans SC, sans-serif" font-size="11.5" fill="#065f46" text-anchor="middle">子 agent 独立后台运行</text>
<path d="M285 226 L285 280 L440 280 L440 306" stroke="#64748b" stroke-width="2" marker-end="url(#arr2)"/>
<path d="M615 226 L615 280 L448 280" stroke="#64748b" stroke-width="2"/>
<rect x="320" y="310" width="240" height="44" rx="22" fill="#dbeafe" stroke="#2563eb" stroke-width="2"/>
<text x="440" y="338" font-family="Noto Sans SC, sans-serif" font-size="12.5" font-weight="600" fill="#1d4ed8" text-anchor="middle">子 agent 运行完成</text>
<line x1="440" y1="354" x2="440" y2="394" stroke="#64748b" stroke-width="2" marker-end="url(#arr2)"/>
<rect x="120" y="398" width="600" height="44" rx="22" fill="#ede9fe" stroke="#7c3aed" stroke-width="2"/>
<text x="420" y="426" font-family="Noto Sans SC, sans-serif" font-size="12.5" font-weight="600" fill="#5b21b6" text-anchor="middle">通知回父：tool_result · 通知注入下一 turn · 邮箱 FINAL_ANSWER</text>
<text x="60" y="482" font-family="Noto Sans SC, sans-serif" font-size="11" fill="#64748b">注：另有内部隐式派生（codex review / guardian / compact / 记忆合并、hermes /review）不经模型工具调用，直接复用同一子运行设施</text>
<line x1="250" y1="510" x2="295" y2="510" stroke="#64748b" stroke-width="2" marker-end="url(#arr2)"/>
<text x="305" y="515" font-family="Noto Sans SC, sans-serif" font-size="11.5" fill="#475569">控制流（左：同步路径 / 右：异步路径）</text>
</svg></div>
<p class="diagram-caption">图 2：创建子 agent 的时机与执行分支（闸门内容：ZCode 结构性禁递归 · hermes pause/深度/oneshot 预算 · codex MultiAgentMode 门控）</p>

**共性**：五家全部是**模型显式工具调用触发**，没有一家有"框架自动拆分任务/上下文过长自动派生"的隐式调度器。派生时机的引导都写在工具描述和系统提示里，由模型自行决策。

- 入口工具命名：ZCode `Agent`（兼容别名 `Task`，`/Users/apple/Desktop/code/ZCode/apps/zcode-cli/packages/core/src/tool/compat.ts:1-4`）；claude-code 同款命名（`/Users/apple/Desktop/code/claude-code/src/tools/AgentTool/constants.ts:1-3`）；kimi-code `Agent`+`AgentSwarm`+`TowerSpawn`（`.../agent/tools/agent/agentTool.ts:106-108`）；codex `spawn_agent`（V2 注册在 `collaboration` 命名空间，`/Users/apple/Desktop/code/codex/codex-rs/core/src/config/mod.rs:256`）；hermes `delegate_task`（`/Users/apple/.hermes/hermes-agent/tools/delegate_tool.py:736-750`）。

**差异点**：

1. **触发门控最严的是 codex**：有显式的 MultiAgentMode 策略——默认 `ExplicitRequestOnly`（"用户明确要求并行/委派才可派生，'要深度/要彻底'不算授权"，`/Users/apple/Desktop/code/codex/codex-rs/core/src/tools/handlers/multi_agents_spec.rs:706-707`），推理档位 `Ultra` 才切 `Proactive`（`/Users/apple/Desktop/code/codex/codex-rs/core/src/session/multi_agents.rs:92-108`）。其余四家只靠工具描述的"When to use"软引导。
2. **批量扇出是一等公民的只有 kimi-code**（`AgentSwarm`，单次最多 128 个，`{{item}}` 模板，`/Users/apple/Desktop/code/kimi-code/packages/agent-core-v2/src/features/swarm/tools/agent-swarm/agent-swarm.ts:7`）和 hermes（`tasks=[...]` 批量数组即并行扇出）。ZCode/claude-code/codex 靠"一条消息多个工具调用"并行。
3. **隐式派生只存在于内部管道**，不面向模型：codex 的 review/guardian(auto_review 审批)/compact/记忆合并 4 类内部子 agent（`run_codex_thread_one_shot`，`/Users/apple/Desktop/code/codex/codex-rs/core/src/codex_delegate.rs`；SubAgentSource 枚举 `/Users/apple/Desktop/code/codex/codex-rs/cli/src/doctor/thread_inventory.rs:677-683`）；hermes 的 `/review`（`/Users/apple/.hermes/hermes-agent/agent/review_engine.py:170-171`）与插件 API `subagent_lifecycle.launch()`。claude-code 唯一"半隐式"是 FORK_SUBAGENT 实验（省略 `subagent_type` 即 fork，`/Users/apple/Desktop/code/claude-code/src/tools/AgentTool/forkSubagent.ts:22-27`）。
4. **续跑（resume）是共同能力但形态不同**：ZCode `SendMessage` 以后台拉起同一 child session（`runner.ts:955`）；kimi `Agent(resume="<agent_id>")` 重建 agent scope 续跑、禁止同一子并发（`agentTool.ts:405-460`）；claude-code `SendMessage` 续接（完整上下文保留，`resumeAgent.ts`）；codex `followup_task`（触发 idle 子的新 turn）/`resume_agent`；hermes 同工具 `action=steer`（中途改道）。
5. **批量前质量闸门是 hermes 独有**：goal 拒绝 `TODO`/模板占位符/多任务下 <10 字符（`/Users/apple/.hermes/hermes-agent/tools/delegate_tool_tasks.py:36-65`），其余四家对 prompt 内容不设质量校验。

### 2.2 子 agent 的上下文管理

<div class="diagram"><svg viewBox="0 0 860 520" style="width:100%;max-width:860px;height:auto;" fill="none">
<defs><marker id="arr3" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6 z" fill="#64748b"/></marker><marker id="arr3g" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6 z" fill="#059669"/></marker></defs>
<rect x="25" y="30" width="255" height="250" rx="16" fill="#f8fafc" stroke="#94a3b8" stroke-width="2"/>
<text x="152" y="60" font-family="Noto Sans SC, sans-serif" font-size="13" font-weight="700" fill="#334155" text-anchor="middle">零继承（全新会话）</text>
<text x="152" y="92" font-family="Noto Sans SC, sans-serif" font-size="11.5" fill="#475569" text-anchor="middle">ZCode · hermes-agent</text>
<text x="152" y="114" font-family="Noto Sans SC, sans-serif" font-size="11.5" fill="#475569" text-anchor="middle">kimi-code（默认）</text>
<text x="152" y="136" font-family="Noto Sans SC, sans-serif" font-size="11.5" fill="#475569" text-anchor="middle">claude-code（默认）</text>
<line x1="55" y1="152" x2="250" y2="152" stroke="#cbd5e1" stroke-width="1"/>
<text x="152" y="180" font-family="Noto Sans SC, sans-serif" font-size="11.5" fill="#64748b" text-anchor="middle">子只见 prompt 一条</text>
<text x="152" y="202" font-family="Noto Sans SC, sans-serif" font-size="11.5" fill="#64748b" text-anchor="middle">prompt 必须自包含</text>
<text x="152" y="224" font-family="Noto Sans SC, sans-serif" font-size="11.5" fill="#64748b" text-anchor="middle">不带父历史 / 父系统提示</text>
<text x="152" y="256" font-family="Noto Sans SC, sans-serif" font-size="11" fill="#94a3b8" text-anchor="middle">继承：cwd / AGENTS.md / 模型 / 权限</text>
<rect x="300" y="30" width="255" height="250" rx="16" fill="#f8fafc" stroke="#94a3b8" stroke-width="2"/>
<text x="427" y="60" font-family="Noto Sans SC, sans-serif" font-size="13" font-weight="700" fill="#334155" text-anchor="middle">可选 fork（参数 / 实验）</text>
<text x="427" y="92" font-family="Noto Sans SC, sans-serif" font-size="11.5" fill="#475569" text-anchor="middle">kimi fork:true（实验 flag）</text>
<text x="427" y="114" font-family="Noto Sans SC, sans-serif" font-size="11.5" fill="#475569" text-anchor="middle">claude-code FORK_SUBAGENT</text>
<text x="427" y="136" font-family="Noto Sans SC, sans-serif" font-size="11.5" fill="#475569" text-anchor="middle">codex fork_turns=N（最近 N 轮）</text>
<line x1="330" y1="152" x2="525" y2="152" stroke="#cbd5e1" stroke-width="1"/>
<text x="427" y="180" font-family="Noto Sans SC, sans-serif" font-size="11.5" fill="#64748b" text-anchor="middle">拷贝父历史快照进子上下文</text>
<text x="427" y="202" font-family="Noto Sans SC, sans-serif" font-size="11.5" fill="#64748b" text-anchor="middle">加免责注记（kimi）</text>
<text x="427" y="224" font-family="Noto Sans SC, sans-serif" font-size="11.5" fill="#64748b" text-anchor="middle">提示清洗防污染（codex）</text>
<text x="427" y="256" font-family="Noto Sans SC, sans-serif" font-size="11" fill="#94a3b8" text-anchor="middle">claude-code fork 连系统提示一并继承</text>
<rect x="575" y="30" width="260" height="250" rx="16" fill="#f8fafc" stroke="#94a3b8" stroke-width="2"/>
<text x="705" y="60" font-family="Noto Sans SC, sans-serif" font-size="13" font-weight="700" fill="#334155" text-anchor="middle">默认全继承</text>
<text x="705" y="92" font-family="Noto Sans SC, sans-serif" font-size="11.5" fill="#475569" text-anchor="middle">codex（fork_turns=all 默认）</text>
<line x1="605" y1="152" x2="805" y2="152" stroke="#cbd5e1" stroke-width="1"/>
<text x="705" y="180" font-family="Noto Sans SC, sans-serif" font-size="11.5" fill="#64748b" text-anchor="middle">全历史 fork（可 N / none）</text>
<text x="705" y="202" font-family="Noto Sans SC, sans-serif" font-size="11.5" fill="#64748b" text-anchor="middle">+ base / developer 指令</text>
<text x="705" y="224" font-family="Noto Sans SC, sans-serif" font-size="11.5" fill="#64748b" text-anchor="middle">+ 审批 / 沙箱 / MCP 快照</text>
<text x="705" y="256" font-family="Noto Sans SC, sans-serif" font-size="11" fill="#94a3b8" text-anchor="middle">剥离父 usage hint 后重建子提示</text>
<line x1="152" y1="282" x2="152" y2="326" stroke="#64748b" stroke-width="2" marker-end="url(#arr3)"/>
<line x1="427" y1="282" x2="427" y2="326" stroke="#64748b" stroke-width="2" marker-end="url(#arr3)"/>
<line x1="705" y1="282" x2="705" y2="326" stroke="#64748b" stroke-width="2" marker-end="url(#arr3)"/>
<rect x="25" y="330" width="810" height="38" rx="19" fill="#f1f5f9" stroke="#64748b" stroke-width="2"/>
<text x="430" y="355" font-family="Noto Sans SC, sans-serif" font-size="12.5" font-weight="600" fill="#334155" text-anchor="middle">结果回传父 agent</text>
<path d="M330 368 L330 406 L235 406 L235 416" stroke="#64748b" stroke-width="2" marker-end="url(#arr3)"/>
<path d="M530 368 L530 406 L625 406 L625 416" stroke="#64748b" stroke-width="2" marker-end="url(#arr3)"/>
<rect x="60" y="420" width="350" height="56" rx="22" fill="#dbeafe" stroke="#2563eb" stroke-width="2"/>
<text x="235" y="444" font-family="Noto Sans SC, sans-serif" font-size="12.5" font-weight="600" fill="#1d4ed8" text-anchor="middle">原文派：最后 assistant 消息原样</text>
<text x="235" y="464" font-family="Noto Sans SC, sans-serif" font-size="11" fill="#1d4ed8" text-anchor="middle">ZCode 120KB · claude-code 100K · kimi · codex</text>
<rect x="450" y="420" width="350" height="56" rx="22" fill="#d1fae5" stroke="#059669" stroke-width="2"/>
<text x="625" y="444" font-family="Noto Sans SC, sans-serif" font-size="12.5" font-weight="600" fill="#065f46" text-anchor="middle">摘要派：预算裁剪 + spill（hermes）</text>
<text x="625" y="464" font-family="Noto Sans SC, sans-serif" font-size="11" fill="#065f46" text-anchor="middle">24000 字符 · 75%头/25%尾 · read_file 指针</text>
<line x1="560" y1="500" x2="605" y2="500" stroke="#059669" stroke-width="2" stroke-dasharray="5 3" marker-end="url(#arr3g)"/>
<text x="615" y="505" font-family="Noto Sans SC, sans-serif" font-size="11.5" fill="#475569">虚线＝不传递 / 实线＝传递（含结果回传）</text>
</svg></div>
<p class="diagram-caption">图 3：三种上下文继承模式与两种结果回传通道</p>

**两大流派**：

- **零上下文派（4/5）**：子 agent 全新会话，只见 prompt 一条，必须自包含。ZCode（`childSessionId = subagent_<agentId>`，`/Users/apple/Desktop/code/ZCode/apps/zcode-cli/packages/core/src/subagent/runner.ts:806`；工具描述明说 "A new Agent call starts fresh"）；claude-code（`promptMessages = [createUserMessage({content: prompt})]`，`AgentTool.tsx:538-540`；"it starts with zero context... Brief the agent like a smart colleague who just walked into the room"，`prompt.ts:103`）；kimi 默认零上下文（"The subagent starts with zero context"，`agent.md:4`）；hermes（fresh conversation + `skip_memory=True, skip_context_files=True`，`/Users/apple/.hermes/hermes-agent/tools/delegate_tool.py:236-248`）。
- **历史继承派（codex，以及三家的实验性 fork）**：codex 默认 `fork_turns=all` 复制父全历史（`/Users/apple/Desktop/code/codex/codex-rs/core/src/tools/handlers/multi_agents_v2/spawn.rs:290-315`），可选最近 N 轮或 `none`；fork 时清洗父级 usage hint、替换 developer 指令片段防父子提示互相污染（`/Users/apple/Desktop/code/codex/codex-rs/core/src/agent/control/spawn.rs:963-996`）。kimi `fork:true`（实验 flag）拷父全历史 + 注入 FORK_CONTEXT_NOTICE "这不是你自己的历史，只作参考"（`spawn.ts:13-14`）；claude-code fork 继承全历史 + 父系统提示（byte-identical 以复用 prompt cache，`AgentTool.tsx:483-512`）。

**继承/隔离清单对比**：

| 项 | ZCode | kimi-code | codex | hermes-agent | claude-code |
|---|---|---|---|---|---|
| 对话历史 | 不继承 | 默认不继承（fork 例外） | **默认继承（all）** | 不继承 | 不继承（fork 例外） |
| 系统提示 | 自建（profile 模板） | 自建（system.md+角色） | **继承父 base instructions** | 自建（goal+context 拼装） | 自建（内置/自定义）；fork 继承父 |
| 项目约定（AGENTS.md/CLAUDE.md） | 注入（injectAgentsMd 可关） | 经 promptPrefix（explore 带 git 上下文） | 并入 base instructions 一起继承 | 按主 agent 同规则补注入（跳过 SOUL.md） | userContext 共享同源（Explore/Plan 主动省略） |
| cwd | 继承 | 继承（会话 cwd） | 继承（turn cwd） | 继承+可选 git worktree 隔离 | 继承/`cwd` 参数/`isolation:"worktree"` |
| 模型/凭证 | 继承父 Model（不可覆盖，刻意） | 继承，可用 secondary model 池覆盖 | 继承，可 model/reasoning_effort 覆盖 | 继承或 delegation.* 配置覆盖 | 继承或 `model` 覆盖（sonnet/opus/haiku） |
| 权限/审批 | Explore 独立 yolo；其余继承父权限服务 | 权限模式镜像父 | 审批策略+沙箱+权限快照继承 | 同父；Kanban 身份 env 擦除 | 父 session 级 allow rules 清空防泄漏（`runAgent.ts:465-479`） |
| 记忆 | profile 级独立持久记忆（非父子共享） | 各自独立 | **对子会话禁用**（`/Users/apple/Desktop/code/codex/codex-rs/memories/README.md:33-35`） | 不读写 MEMORY.md（skip_memory） | 可选 agent 持久记忆（user/project/local） |

**结果回传是差异最大的一维**——"原文派" vs "摘要派"：

- 原文派（子的最后一条 assistant 消息原样，不改写）：ZCode 120KB 上限（`MAX_AGENT_MODEL_BYTES = 120_000`，超限 artifact+head 预览，`/Users/apple/Desktop/code/ZCode/apps/zcode-cli/packages/core/src/tool/handlers/agent.ts:21`）；claude-code 100K 字符（`maxResultSizeChars: 100_000`，`AgentTool.tsx:229`）；kimi（`latestAssistantText`，`runAgentTurn.ts:73`）；codex（FINAL_ANSWER = 最终消息原文，仅错误文本截 ~900 token，`/Users/apple/Desktop/code/codex/codex-rs/core/src/session_prefix.rs:24-35`）。
- 摘要派（只有 hermes）：父只拿 `final_response`，且按预算裁剪——默认 24000 字符（`DEFAULT_MAX_SUMMARY_CHARS`，`/Users/apple/.hermes/hermes-agent/tools/delegate_tool_results.py:160`），超限 75%头+25%尾 + 全文 spill 到磁盘 + `read_file offset=` 指针（`delegate_tool_results.py:187-223`）；子的中间工具调用/推理**永远不进父上下文**，只回传脱敏 `tool_trace` 元数据（`delegate_tool_child_run.py:521-551`）。
- 中间过程可见性：ZCode 把子的工具/权限事件镜像到父 timeline（raw 正文不进，`tool-event-mirror.ts:19-25`）；hermes 后台任务有实时 transcript 文件可查但不进上下文；其余主要靠 UI 侧事件流。

### 2.3 子 agent 的输入输出内容

**输入**（模型面 schema）：

- 共同骨架：`description`（3-5 词短描述，UI 用）+ `prompt`（任务全文，唯一任务载体）。文件路径/命令都要求写进 prompt 文本——**五家全部没有真正的附件上传字段**（唯 codex V1 有 `items` 结构化附件支持 text/image_url/audio_url/path/name，`/Users/apple/Desktop/code/codex/codex-rs/core/src/tools/handlers/multi_agents_spec.rs:560-583`；hermes 有 `images≤8` 的本地路径/URL 列表，`/Users/apple/.hermes/hermes-agent/tools/delegate_tool_tasks.py:124-147`）。
- 控制字段差异：ZCode 刻意**不暴露 model**（`contracts/src/tools/agent.ts:25-26` 注释）；kimi/claude-code/codex 均可覆盖 model；codex 需要 `task_name`（构成 `/root/...` 任务路径树）；hermes 输入是**批量数组** `tasks=[{goal,context,output_schema,images,group}]`，且独有：
  - `context` 与 `goal` 分离（goal=任务、context=该子专属背景）；
  - `output_schema`（JSON Schema 输出契约，注入 "OUTPUT CONTRACT" 块，父用 jsonschema 校验，失败仅一次有界重试，`/Users/apple/.hermes/hermes-agent/tools/delegation_output_schema.py:45-57,109-115`）。
- 自定义补充：kimi profile 可配 `promptPrefix` 自动前置（explore 前置 git 上下文，`profiles.ts:110-125`）。

**输出**（回传父的形态）：

- 结构化 output schema：ZCode `AgentCompletedOutput{status,agentId,content:[text],totalToolUseCount,totalDurationMs,totalTokens,usage}` / `AgentBackgroundedOutput{async_launched,outputFile}`（`contracts/src/tools/agent.ts:44-70`）；claude-code 同款 union（`agentToolUtils.ts:227-258`）。
- 文本格式化：kimi `agent_id/actual_subagent_type/status/stop_reason + [summary] + resume_hint`（`agentTool.ts:756-773`），Swarm 输出 `<agent_swarm_result>` XML。
- JSON 结果条目：hermes `{results:[{task_index,status,summary,exit_reason,truncated,tokens,tool_trace,cost_usd,schema_valid,…}], total_duration_seconds}`（`delegate_tool_child_run.py:553-650`）；后台先返回 dispatch handle（`{status:"dispatched", subagent_ids, live_transcripts}`），完成后整包作为新消息再入会话。
- 消息协议型：codex `spawn_agent` 只返回 `{task_name,nickname}`（默认 hide metadata 只给 task_name），**结果本体走邮箱消息** `Message Type: FINAL_ANSWER\nTask name:…\nSender:…\nPayload:…`（`/Users/apple/Desktop/code/codex/codex-rs/core/src/context/inter_agent_completion_message.rs:40-45`）。
- 落盘 artifact：ZCode 每个 agent 写 `metadata.json`/`output.txt`/`task.output`（`runner.ts:808-815`）；hermes 全文 spill + 实时 transcript（`cache/delegation/live/<id>/task-<n>.log`）；claude-code/kimi 后台任务写输出文件，通知带指针。

### 2.4 子 agent 的系统提示词

三种构造哲学：

1. **专属轻提示（ZCode / kimi / claude-code / hermes）**：给子一套独立的短系统提示，不给父的完整系统提示。
   - ZCode 4 层拼装：profile 模板（general-purpose `/Users/apple/Desktop/code/ZCode/apps/zcode-cli/packages/core/src/subagent/general-purpose.ts:7-24` "You are an agent for ZCode CLI... respond with a concise report"；Explore `explore.ts:20-68` "READ-ONLY MODE - NO FILE MODIFICATIONS"）+ 公共 Notes（绝对路径、"Do NOT Write report .md files... the parent agent reads your text output"，`system-prompt.ts:10-19`）+ 环境块 + 可选记忆模板（`context-builder.ts:106-163`）。
   - kimi：共享模板 `system.md` + 子 agent 专属 `TASK_AGENT_ROLE_PREFIX`（`/Users/apple/Desktop/code/kimi-code/packages/agent-core-v2/src/app/agentProfileCatalog/profile-shared.ts:14-18`）："You are now running as a subagent. All the user messages are sent by the main agent. The main agent cannot see your context, it can only see your last message... Do not directly ask the end user questions."；coder 角色再要求"最终消息就是全部交接"（`profiles.ts:82-88`）。
   - claude-code：内置类型是 TS 常量（`/Users/apple/Desktop/code/claude-code/src/tools/AgentTool/built-in/`：general-purpose / Explore 只读 / Plan 架构 / verification 对抗验证收 `VERDICT: PASS|FAIL|PARTIAL` / claude-code-guide），自定义 `.claude/agents/*.md` 正文即系统提示（`loadAgentsDir.ts:713-732`）；fork worker 固定 boilerplate："You are a forked worker process. You are NOT the main agent... Do NOT spawn sub-agents"（`forkSubagent.ts:171-198`）。
   - hermes：`_build_child_system_prompt`（`/Users/apple/.hermes/hermes-agent/tools/delegate_tool_progress.py:178-217`）="You are a focused subagent working on a specific delegated task." + CONTEXT + WORKSPACE PATH + 完成指令（"Your response is returned to the parent agent as a summary, and overlong summaries crowd out the parent's context window"）；goal 特意放首条 user 消息而不进系统提示；orchestrator 追加 "Subagent Spawning" 授权块 + 深度真值注记（"You are at depth N... max_spawn_depth=X"，防止模型臆造嵌套能力）。
2. **继承+增补（codex 独有）**：协作子 agent **没有独立系统提示**，继承父 base instructions（含 AGENTS.md）+ developer instructions；专属内容只是一段 developer 角色 usage hint（`DEFAULT_MULTI_AGENT_V2_SUBAGENT_USAGE_HINT_TEXT`，`/Users/apple/Desktop/code/codex/codex-rs/prompts/src/model_messages/multi_agent.rs:27-45`："You are an agent in a team of agents... When you provide a response in the final channel, that content is immediately delivered back to your parent agent."），包 `<multi_agent_role>` 注入，可被模型目录或 `subagent_usage_hint_text` 配置覆盖。理念：**多 agent 团队成员能力同构**（"All agents... are equally intelligent and capable, and have access to the same set of tools"）。
3. **整体替换（各框架的内部专用子 agent）**：codex review 用 `/Users/apple/Desktop/code/codex/codex-rs/prompts/templates/review/rubric.md`、guardian 用 `prompts/templates/guardian/policy.md`。

**共性内容**：① 明确"你服务于调用方而非最终用户"（kimi 最直白）；② 最终消息=唯一回传物，要求精炼/交接完整；③ 环境事实（cwd/平台/只读约束）。**差异**：ZCode/claude-code 用"concise report"导向（父负责转述），kimi coder 用"完整技术交接"导向（改了什么/为何/验证/未尽事项），hermes 用"summary + 预算感知"导向。

### 2.5 子 agent 的工具范围

<div class="diagram"><svg viewBox="0 0 840 500" style="width:100%;max-width:840px;height:auto;" fill="none">
<defs><marker id="arr4" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6 z" fill="#94a3b8"/></marker></defs>
<rect x="25" y="30" width="255" height="130" rx="16" fill="#eff6ff" stroke="#2563eb" stroke-width="2"/>
<text x="152" y="58" font-family="Noto Sans SC, sans-serif" font-size="13" font-weight="700" fill="#1d4ed8" text-anchor="middle">白名单制（声明 / 重建）</text>
<text x="152" y="86" font-family="Noto Sans SC, sans-serif" font-size="11.5" fill="#475569" text-anchor="middle">ZCode：通配 * 展开父面 / Explore 只读 7 工具</text>
<text x="152" y="110" font-family="Noto Sans SC, sans-serif" font-size="11.5" fill="#475569" text-anchor="middle">kimi：profile 工具表（coder 有写无派生）</text>
<text x="152" y="134" font-family="Noto Sans SC, sans-serif" font-size="11.5" fill="#475569" text-anchor="middle">claude-code：工具池独立重建再过滤</text>
<rect x="305" y="30" width="230" height="130" rx="16" fill="#ecfdf5" stroke="#059669" stroke-width="2"/>
<text x="420" y="58" font-family="Noto Sans SC, sans-serif" font-size="13" font-weight="700" fill="#065f46" text-anchor="middle">继承减法（hermes）</text>
<text x="420" y="86" font-family="Noto Sans SC, sans-serif" font-size="11.5" fill="#475569" text-anchor="middle">父工具集原样继承</text>
<text x="420" y="110" font-family="Noto Sans SC, sans-serif" font-size="11.5" fill="#475569" text-anchor="middle">减 5 禁用工具（含 delegate_task）</text>
<text x="420" y="134" font-family="Noto Sans SC, sans-serif" font-size="11.5" fill="#475569" text-anchor="middle">剔 delegation / kanban 整套</text>
<rect x="560" y="30" width="255" height="130" rx="16" fill="#ede9fe" stroke="#7c3aed" stroke-width="2"/>
<text x="687" y="58" font-family="Noto Sans SC, sans-serif" font-size="13" font-weight="700" fill="#5b21b6" text-anchor="middle">全继承（codex）</text>
<text x="687" y="86" font-family="Noto Sans SC, sans-serif" font-size="11.5" fill="#475569" text-anchor="middle">same tools as you（同套工具）</text>
<text x="687" y="110" font-family="Noto Sans SC, sans-serif" font-size="11.5" fill="#475569" text-anchor="middle">MCP / skills / plugins 同源继承</text>
<text x="687" y="134" font-family="Noto Sans SC, sans-serif" font-size="11.5" fill="#475569" text-anchor="middle">靠深度 / 并发约束而非裁剪</text>
<text x="420" y="230" font-family="Noto Sans SC, sans-serif" font-size="13" font-weight="700" fill="#334155" text-anchor="middle">防递归深度谱系（硬约束 → 软约束）</text>
<line x1="80" y1="320" x2="780" y2="320" stroke="#94a3b8" stroke-width="2" marker-end="url(#arr4)"/>
<circle cx="130" cy="320" r="7" fill="#dc2626"/>
<circle cx="280" cy="320" r="7" fill="#d97706"/>
<circle cx="430" cy="320" r="7" fill="#059669"/>
<circle cx="580" cy="320" r="7" fill="#2563eb"/>
<circle cx="730" cy="320" r="7" fill="#7c3aed"/>
<text x="130" y="300" font-family="Noto Sans SC, sans-serif" font-size="11.5" font-weight="600" fill="#334155" text-anchor="middle">结构性 1 层</text>
<text x="280" y="300" font-family="Noto Sans SC, sans-serif" font-size="11.5" font-weight="600" fill="#334155" text-anchor="middle">默认 1 层</text>
<text x="430" y="300" font-family="Noto Sans SC, sans-serif" font-size="11.5" font-weight="600" fill="#334155" text-anchor="middle">结构性 2 层</text>
<text x="580" y="300" font-family="Noto Sans SC, sans-serif" font-size="11.5" font-weight="600" fill="#334155" text-anchor="middle">V1 ＝ 1 层</text>
<text x="730" y="300" font-family="Noto Sans SC, sans-serif" font-size="11.5" font-weight="600" fill="#334155" text-anchor="middle">V2 可递归</text>
<text x="130" y="352" font-family="Noto Sans SC, sans-serif" font-size="11" fill="#64748b" text-anchor="middle">ZCode</text>
<text x="130" y="370" font-family="Noto Sans SC, sans-serif" font-size="11" fill="#64748b" text-anchor="middle">（子无派生端口）</text>
<text x="280" y="352" font-family="Noto Sans SC, sans-serif" font-size="11" fill="#64748b" text-anchor="middle">claude-code / hermes</text>
<text x="280" y="370" font-family="Noto Sans SC, sans-serif" font-size="11" fill="#64748b" text-anchor="middle">（禁 Agent / delegate_task）</text>
<text x="430" y="352" font-family="Noto Sans SC, sans-serif" font-size="11" fill="#64748b" text-anchor="middle">kimi</text>
<text x="430" y="370" font-family="Noto Sans SC, sans-serif" font-size="11" fill="#64748b" text-anchor="middle">（类型级剔除可派生目标）</text>
<text x="580" y="352" font-family="Noto Sans SC, sans-serif" font-size="11" fill="#64748b" text-anchor="middle">codex V1</text>
<text x="580" y="370" font-family="Noto Sans SC, sans-serif" font-size="11" fill="#64748b" text-anchor="middle">（超限拒绝派生）</text>
<text x="730" y="352" font-family="Noto Sans SC, sans-serif" font-size="11" fill="#64748b" text-anchor="middle">codex V2</text>
<text x="730" y="370" font-family="Noto Sans SC, sans-serif" font-size="11" fill="#64748b" text-anchor="middle">（4 并发槽约束）</text>
<text x="420" y="440" font-family="Noto Sans SC, sans-serif" font-size="11.5" fill="#475569" text-anchor="middle">圆点＝各家深度限制方案；轴向＝从结构硬约束到纯运行时约束</text>
</svg></div>
<p class="diagram-caption">图 4：工具授予三模型与防递归深度谱系</p>

三种授予模型：

| 模型 | 框架 | 细节 |
|---|---|---|
| **白名单声明制** | ZCode / kimi / claude-code | agent profile 声明 `tools`（支持 `*`）/`disallowedTools`。ZCode：general-purpose `["*"]` 展开为父工具面（剔除 Agent/Task），Explore 固定 7 只读工具（`explore-tools.ts:4-12`，注释明言"只读语义靠 prompt 约束，Bash 是唯一副作用入口"）；kimi：coder 有读写/Bash/mcp 无派生工具、explore 仅只读（`profiles.ts:46-80`）；claude-code：工具池**独立重建**（`assembleToolPool`，"Workers always get their tools from their own permission mode, so they aren't affected by the parent's tool restrictions"，`AgentTool.tsx:568-577`），再按 tools/disallowedTools 过滤，后台 agent 另有更窄白名单 `ASYNC_AGENT_ALLOWED_TOOLS`（`/Users/apple/Desktop/code/claude-code/src/constants/tools.ts:55-71`） |
| **继承减法制** | hermes-agent | 父工具集原样继承（`toolsets=None, # always inherit`，`delegate_tool.py:390-391`），减去 `DELEGATE_BLOCKED_TOOLS = {delegate_task, clarify, memory, send_message, cronjob_manage}`（`/Users/apple/.hermes/hermes-agent/tools/delegate_tool_toolsets.py:14-22`）+ 整套剔除 delegation/kanban；"Children never gain tools the parent lacks" |
| **全继承制** | codex | "The spawned agent will have the same tools as you"（`multi_agents_spec.rs:763`）；MCP/skills/plugins/exec policy 同源继承，靠深度/并发约束而非工具裁剪 |

**防递归（深度）设计谱系**——从硬到软：

1. ZCode **结构性关闭**：child runtime `subagents: {enabled: false}` → SubagentPort 不存在 → 调 Agent 报错（`/Users/apple/Desktop/code/ZCode/apps/zcode-cli/packages/core/src/runtime/methods/subagent.ts:284-287`）。深度固定 **1**。
2. claude-code **默认禁用** `Agent` 工具（"Blocked to prevent recursion"），仅 `USER_TYPE==='ant'` 放开嵌套且无显式深度上限；fork 子孙再 fork 调用时被拒（`AgentTool.tsx:332-334`）。默认深度 **1**。
3. kimi **结构性 2 层**：内置子 profile 无派生工具 + `withoutDelegatingTargets` 在 planSpawn 时剔除"自己还能派生"的目标类型（`/Users/apple/Desktop/code/kimi-code/packages/agent-core-v2/src/app/agentProfileCatalog/profile-shared.ts:75-94`）。无全局深度常量。
4. hermes **默认 1 可配**：`MAX_DEPTH = 1  # flat by default`（`/Users/apple/.hermes/hermes-agent/tools/delegate_tool_config.py:21`），`max_spawn_depth` 可调高无硬顶；role 由深度派生（depth 未满的子自动成 orchestrator 拿回 delegate_task），模型不可选。
5. codex **版本分裂**：V1 `agent_max_depth` 默认 1，超限直接报 "Agent depth limit reached. Solve the task yourself."（`/Users/apple/Desktop/code/codex/codex-rs/core/src/config/mod.rs:261`）；**V2 明确允许子再生子**（"those sub-agents can spawn their own sub-agents"，spawn 处理器无深度检查），靠并发槽约束；内部 delegate 则禁 Collab/MultiAgentV2 防递归。

**沙箱/权限差异**：ZCode Explore 独立 PermissionService+yolo、项目级 profile 禁 frontmatter 提权（`profile.ts:183-185`）；claude-code 子 agent 不继承父 session allow rules（防泄漏）；hermes 可选 git worktree 文件系统隔离 + Kanban 身份擦除（`agent/delegation_context.py:102-118`）；kimi 明言 "The environment is not a sandbox"，explore 只读仅 prompt-enforced；codex 协作子与父共享审批/沙箱快照，但内部 delegate 强制 `approval_policy=never`（`codex_delegate.rs:63-68`）。

### 2.6 子 agent 的运行方式（同步/异步）

<div class="diagram"><svg viewBox="0 0 840 620" style="width:100%;max-width:840px;height:auto;" fill="none">
<defs><marker id="arr5" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6 z" fill="#64748b"/></marker><marker id="arr5p" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6 z" fill="#7c3aed"/></marker></defs>
<rect x="25" y="30" width="385" height="520" rx="16" fill="#eff6ff" stroke="#2563eb" stroke-width="2"/>
<text x="217" y="58" font-family="Noto Sans SC, sans-serif" font-size="12.5" font-weight="700" fill="#1d4ed8" text-anchor="middle">同步模式（ZCode / kimi / claude-code 默认）</text>
<rect x="68" y="80" width="300" height="40" rx="20" fill="#dbeafe" stroke="#2563eb" stroke-width="2"/>
<text x="218" y="105" font-family="Noto Sans SC, sans-serif" font-size="12" font-weight="600" fill="#1d4ed8" text-anchor="middle">父 turn 内调用派生工具</text>
<line x1="218" y1="120" x2="218" y2="156" stroke="#64748b" stroke-width="2" marker-end="url(#arr5)"/>
<rect x="68" y="160" width="300" height="40" rx="20" fill="#fef3c7" stroke="#d97706" stroke-width="2"/>
<text x="218" y="185" font-family="Noto Sans SC, sans-serif" font-size="12" font-weight="600" fill="#92400e" text-anchor="middle">阻塞 await 子 agent 运行</text>
<line x1="218" y1="200" x2="218" y2="236" stroke="#64748b" stroke-width="2" marker-end="url(#arr5)"/>
<rect x="58" y="240" width="320" height="40" rx="20" fill="#d1fae5" stroke="#059669" stroke-width="2"/>
<text x="218" y="265" font-family="Noto Sans SC, sans-serif" font-size="12" font-weight="600" fill="#065f46" text-anchor="middle">子完成 → tool_result（原文/摘要）</text>
<line x1="218" y1="280" x2="218" y2="316" stroke="#64748b" stroke-width="2" marker-end="url(#arr5)"/>
<rect x="68" y="320" width="300" height="40" rx="20" fill="#dbeafe" stroke="#2563eb" stroke-width="2"/>
<text x="218" y="345" font-family="Noto Sans SC, sans-serif" font-size="12" font-weight="600" fill="#1d4ed8" text-anchor="middle">父 turn 继续（上下文连续）</text>
<text x="55" y="410" font-family="Noto Sans SC, sans-serif" font-size="11" fill="#64748b">· claude-code：120s 自动转后台</text>
<text x="55" y="432" font-family="Noto Sans SC, sans-serif" font-size="11" fill="#64748b">· ZCode：autoBackgroundMs 可转后台</text>
<text x="55" y="454" font-family="Noto Sans SC, sans-serif" font-size="11" fill="#64748b">· kimi：run_in_background 可选异步</text>
<text x="55" y="476" font-family="Noto Sans SC, sans-serif" font-size="11" fill="#64748b">· 卡死治理：看门狗 / 2h 超时 / maxTurns</text>
<rect x="430" y="30" width="385" height="520" rx="16" fill="#f5f3ff" stroke="#7c3aed" stroke-width="2"/>
<text x="622" y="58" font-family="Noto Sans SC, sans-serif" font-size="12.5" font-weight="700" fill="#5b21b6" text-anchor="middle">异步模式（hermes 强制 / codex 天生）</text>
<rect x="468" y="80" width="300" height="40" rx="20" fill="#ede9fe" stroke="#7c3aed" stroke-width="2"/>
<text x="618" y="105" font-family="Noto Sans SC, sans-serif" font-size="12" font-weight="600" fill="#5b21b6" text-anchor="middle">调用即返回 handle / task_name</text>
<line x1="618" y1="120" x2="618" y2="156" stroke="#7c3aed" stroke-width="2" marker-end="url(#arr5p)"/>
<rect x="468" y="160" width="300" height="40" rx="20" fill="#ede9fe" stroke="#7c3aed" stroke-width="2"/>
<text x="618" y="185" font-family="Noto Sans SC, sans-serif" font-size="12" font-weight="600" fill="#5b21b6" text-anchor="middle">父 turn 继续（不阻塞）</text>
<line x1="618" y1="200" x2="618" y2="236" stroke="#7c3aed" stroke-width="2" marker-end="url(#arr5p)"/>
<rect x="458" y="240" width="320" height="40" rx="20" fill="#d1fae5" stroke="#059669" stroke-width="2"/>
<text x="618" y="265" font-family="Noto Sans SC, sans-serif" font-size="12" font-weight="600" fill="#065f46" text-anchor="middle">子 agent 后台独立运行</text>
<line x1="618" y1="280" x2="618" y2="316" stroke="#7c3aed" stroke-width="2" marker-end="url(#arr5p)"/>
<rect x="468" y="320" width="300" height="40" rx="20" fill="#ede9fe" stroke="#7c3aed" stroke-width="2"/>
<text x="618" y="345" font-family="Noto Sans SC, sans-serif" font-size="12" font-weight="600" fill="#5b21b6" text-anchor="middle">完成 → 通知事件（不打断当前 turn）</text>
<line x1="618" y1="360" x2="618" y2="396" stroke="#7c3aed" stroke-width="2" marker-end="url(#arr5p)"/>
<rect x="458" y="400" width="320" height="40" rx="20" fill="#ede9fe" stroke="#7c3aed" stroke-width="2"/>
<text x="618" y="425" font-family="Noto Sans SC, sans-serif" font-size="12" font-weight="600" fill="#5b21b6" text-anchor="middle">注入父的下一 turn（新消息/邮箱）</text>
<text x="460" y="480" font-family="Noto Sans SC, sans-serif" font-size="11" fill="#64748b">· hermes：completion_queue 回合间投递</text>
<text x="460" y="502" font-family="Noto Sans SC, sans-serif" font-size="11" fill="#64748b">· codex：邮箱 trigger_turn=false + wait_agent</text>
<text x="460" y="524" font-family="Noto Sans SC, sans-serif" font-size="11" fill="#64748b">· 控制面：steer / stop / SendMessage 续接</text>
<line x1="250" y1="585" x2="295" y2="585" stroke="#64748b" stroke-width="2" marker-end="url(#arr5)"/>
<text x="305" y="590" font-family="Noto Sans SC, sans-serif" font-size="11.5" fill="#475569">同步控制流</text>
<line x1="450" y1="585" x2="495" y2="585" stroke="#7c3aed" stroke-width="2" marker-end="url(#arr5p)"/>
<text x="505" y="590" font-family="Noto Sans SC, sans-serif" font-size="11.5" fill="#475569">异步事件流（结果延迟送达）</text>
</svg></div>
<p class="diagram-caption">图 5：同步 vs 异步运行方式与结果送达通道</p>

| | 默认形态 | 转后台机制 | 并发上限 | 超时 | 回父通知 |
|---|---|---|---|---|---|
| ZCode | 同步阻塞（await 子运行时） | `run_in_background` / profile `background` / `autoBackgroundMs` 自动转 | 无专门上限；工具调度 10（`scheduler.ts:48`） | 工具级 `timeout:none` + 600s 空闲看门狗（`DEFAULT_MODEL_STREAM_IDLE_TIMEOUT_MS=600_000`）；maxTurns 缺省 4 | `<task-notification>` XML 注入父命令队列（120k 截断，`notification.ts:144-158`）+ SubagentStopped/BackgroundTaskCompleted 事件 |
| kimi-code | 同步阻塞（`waitForForegroundRelease`，`agentTool.ts:566-578`） | `run_in_background`（需 TaskList/TaskOutput/TaskStop 在位，`agentTool.ts:143-146`） | Swarm 128，启动节流（5 个后每 700ms，`agentRunBatch.ts:39-40`）；后台总数受 maxRunningTasks，超限 `TASK_LIMIT_EXCEEDED` | 默认 2h（`DEFAULT_SUBAGENT_TIMEOUT_MS`，`configSection.ts:50`）+ maxSteps/max_tokens | 合成 user 消息 `<notification>` XML 自动入后续 turn（"you do not need to poll"，`taskService.ts:1112-1118`） |
| codex | **异步非阻塞**（spawn 投递 NEW_TASK 即返回，子在自己线程循环跑，`spawn.rs:802-836`） | 天生后台；`wait_agent` 为唯一阻塞点（默认 30s/最小 10s/最大 1h，`config/mod.rs:253-255`） | V2 并发 4 槽含 root（`DEFAULT_MULTI_AGENT_V2_MAX_CONCURRENT_THREADS_PER_SESSION=4`）；V1 总线程 6（`DEFAULT_AGENT_MAX_THREADS=Some(6)`，超限 `AgentLimitReached`）；V2 有空闲逐出/恢复 residency | 无运行超时 | FINAL_ANSWER 以 `trigger_turn=false` 投父邮箱（**不打断父的 turn**，`completion.rs:88-113`）+ `<subagent_notification>`/SubAgentActivity |
| hermes-agent | **顶层强制异步**（`background=not (depth>0)`，schema 的 background 参数被故意忽略，`run_agent.py:1350-1357`）；orchestrator 再派生强制同步 | 天生后台；one-shot/cron/池满自动**降级同步**并附 note（`delegate_tool_dispatch.py:240-274,451-456`） | `max_concurrent_children` 默认 10（`delegate_tool_config.py:17`）；**池满拒绝不排队**（`async_delegation.py:561-565`）；oneshot 会话总量默认 2 | 默认无墙钟超时（`DEFAULT_CHILD_TIMEOUT=None`）；心跳陈旧判定：空闲 450s / 同一工具内 1200s 判死（`delegate_tool.py:72-78`）；可选 `child_timeout_seconds` 无进展预算（80% 处 steer 预警） | `type="async_delegation"` 事件入 completion_queue，**回合之间**作为新消息回父（`async_delegation.py:2-8`）；`action=list/steer/stop` 同步控制面 |
| claude-code | 同步阻塞 | `run_in_background` / `background:true` / 120s 自动转后台（`AgentTool.tsx:70-77`）；fork 开启时强制全异步；后台 agent 独立 AbortController（ESC 不杀，`AgentTool.tsx:686-698`） | 无专门上限；工具并发默认 10（`toolOrchestration.ts:8-12`）；`isConcurrencySafe=true` 鼓励并行 | 无时间超时；maxTurns（frontmatter）+ TaskOutput 等待 30s~600s | `<task-notification>` XML 以 user-role 排队消息注入（"They look like user messages but are not"，`coordinatorMode.ts:144`）；TaskStop kill 时回传部分结果 |

**关键差异**：

1. **"谁决定异步"**：ZCode/kimi/claude-code 是**模型可选**（run_in_background 参数）；codex 是**天生异步**（协作语义决定）；hermes 是**框架强制**（模型无从选择，防阻塞父 turn）。
2. **通知注入语义**：codex 的 `trigger_turn=false` 最克制（父不被打断、下次活动时读取）；ZCode/claude-code 的 `<task-notification>` 与 kimi 的 `<notification>` 都是"下一 turn 自动出现在对话里"；hermes 走完成队列在回合间投递（与去重/崩溃恢复共用一套机制）。
3. **卡死治理哲学不同**：ZCode 用空闲看门狗（600s）硬杀；kimi 用 2h 硬超时；hermes 显式放弃墙钟超时（"legitimate heavy work was being killed mid-task"，`delegate_tool_config.py:24-27`），改用心跳陈旧判定；codex/claude-code 干脆没有时间维度限制，只有轮次限制。
4. **双向通信**：ZCode 有 `SendMessage`（父→子）+ `RespondToCoordinator`（子→父主动汇报）；codex 有完整邮箱（`send_message` 不触发 turn / `followup_task` 触发 turn / `send_input`）；hermes 有 `steer`（追加到子下一个工具结果，不打断当前工具）；kimi/claude-code 只有 resume 续跑。

---

## 3. 设计光谱

**上下文继承**：全零继承（ZCode ≈ hermes ≈ claude-code 默认 ≈ kimi 默认）←——→ 全继承（codex 默认 fork_turns=all ≈ claude-code/kimi fork 实验）
**结果回传**：原文（claude-code 100K / ZCode 120KB / kimi / codex）←——→ 摘要+预算+spill（hermes 独有）
**工具授予**：白名单重建（claude-code）←——→ 白名单声明（ZCode/kimi）←——→ 继承减法（hermes）←——→ 全继承（codex）
**运行模型**：同步阻塞默认（ZCode/kimi/claude-code）←——→ 强制/天生异步（hermes/codex）
**递归深度**：结构性 1（ZCode）/ 默认 1（claude-code/hermes）/ 结构性 2（kimi）/ V1=1、V2 无限（codex）
**角色能力同构性**：异构（ZCode/kimi/claude-code 的 Explore/Plan/verification 专职裁剪）←——→ 同构（codex "equally intelligent... same tools"；hermes 仅 leaf/orchestrator 之分）

## 4. 可借鉴模式（对 chat-agent 类 Agent 产品的启示)

1. **"最终消息=唯一交付物"必须写进提示词并配预算**：五家都把"父只看到你最后一条消息"显式写进子的提示（kimi `TASK_AGENT_ROLE_PREFIX` 最完整）；hermes 进一步在提示里做预算教育（"overlong summaries crowd out the parent's context window"）+ 机械裁剪（75/25 + spill + read_file 指针），提示词与机制双保险。
2. **防递归用结构而非嘱咐**：ZCode 直接不给子 agent 装 SubagentPort、kimi 用 `withoutDelegatingTargets` 类型级剔除，都比"提示词里写不许再派生"（claude-code fork worker）可靠。深度/角色由框架按深度派生（hermes）优于交给模型选择。
3. **fork 时的提示清洗**：codex fork 历史时剥离父级 usage hint、替换 developer 指令片段（`spawn.rs:963-996`）；kimi fork 加"这不是你的历史"免责注记——继承历史就必须防提示污染与身份混淆。
4. **结构化输出契约**（hermes `output_schema` + OUTPUT CONTRACT + 一次有界重试）是把子 agent 从"文本劳工"变"可组合组件"的关键，五家中仅此一家。
5. **卡死治理选"心跳陈旧"而非墙钟超时**（hermes），或至少像 kimi 一样给软性大超时（2h）+ resume 续跑兜底；硬短超时（如 ZCode 600s 空闲）对长工具任务有误杀风险。
6. **通知不打断父 turn**（codex `trigger_turn=false` / hermes 回合间投递）比"下一轮自动注入 user 消息"（ZCode/claude-code/kimi）对父上下文更友好，但需要显式等待/读取机制配合。
7. **后台任务的"拒绝不排队"**（hermes `async_delegation.py:561-565`）+ 满则同步降级，防止失控模型无限堆积后台工作——比 kimi 的排队节流更保守可控。

## 5. 附录

- 逐框架完整报告（含全部代码摘录、证据链与关键文件清单）：
  - `/Users/apple/Desktop/code/chat-agent/docs/multiple_agent/notes/zcode.md`
  - `/Users/apple/Desktop/code/chat-agent/docs/multiple_agent/notes/kimi-code.md`
  - `/Users/apple/Desktop/code/chat-agent/docs/multiple_agent/notes/codex.md`
  - `/Users/apple/Desktop/code/chat-agent/docs/multiple_agent/notes/hermes-agent.md`
  - `/Users/apple/Desktop/code/chat-agent/docs/multiple_agent/notes/claude-code.md`
- 分析基准日期：2026-09-22（行号以当日代码为准）。
- 常量抽查已复核：`MAX_AGENT_MODEL_BYTES = 120_000`、`MAX_AGENT_SWARM_SUBAGENTS = 128`、`DEFAULT_SUBAGENT_TIMEOUT_MS = 2h`、`DEFAULT_AGENT_MAX_DEPTH = 1`、`DEFAULT_MULTI_AGENT_V2_MAX_CONCURRENT_THREADS_PER_SESSION = 4`、`DEFAULT_AGENT_MAX_THREADS = 6`、`DELEGATE_BLOCKED_TOOLS`、`DEFAULT_MAX_SUMMARY_CHARS = 24000`、`MAX_DEPTH = 1`、`ALL_AGENT_DISALLOWED_TOOLS`、`maxResultSizeChars: 100_000` 均与源码一致。
