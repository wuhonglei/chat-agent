---
name: "self-improving-agent"
description: "Cursor 版自进化技能：把会话中的有效经验沉淀为可复用知识。支持记忆体检、规则晋升、技能提取与显式记忆写入。适用场景：复盘近期改动、把高频模式升级为规则、把排障方案抽成技能、治理记忆冗余与过期内容。"
---

# Self-Improving Agent (Cursor Edition)

> Capture -> Curate -> Enforce -> Reuse

本技能用于 Cursor 编辑器中的 Agent 工作流：将临时经验持续沉淀为长期有效的工程知识，并把高价值方案转化为规则或独立技能。

## 目标与边界

- 目标
  - 识别高频、稳定、可验证的做法
  - 将做法晋升为项目规则或可复用技能
  - 控制记忆体噪声，避免上下文浪费
- 非目标
  - 不为一次性临时方案建立永久规则
  - 不把未经验证的猜测写入长期记忆
  - 不替代正常代码评审和测试

## 在 Cursor 中何时触发

满足任一条件时应主动触发本技能：

- 刚完成一次复杂改造或排障，且有可复用结论
- 同类问题在近几次会话重复出现 2 次以上
- 发现现有规则与实际代码习惯不一致
- 记忆文件明显膨胀，出现过期路径、失效约定或重复条目

## Cursor 适配的知识分层

在 Cursor 项目中按短期到长期管理知识：

- 会话上下文（短期）
  - 当前对话与编辑历史中的即时结论
  - 用于当前任务推进，不默认长期保留
- 项目规则（长期、强约束）
  - 放入项目级规则文件（如 `.cursorrules` 或团队约定文件）
  - 只收录稳定、可执行、可验证的规则
- 可复用技能（长期、可迁移）
  - 以 `SKILL.md + 示例 + 参考文档` 形式沉淀
  - 面向跨项目复用的模式化方案

## 核心流程（Cursor Agent 执行）

### 1) Review：记忆体检

输入：

- 最近完成的任务、错误修复、重构记录
- 相关记忆文件与规则文件

检查维度：

- 重复出现：是否跨会话、跨文件反复出现
- 稳定性：是否适用于主干场景，而非一次性例外
- 可验证性：是否可通过 lint、test、build 或运行结果证明
- 维护成本：是否会增加认知负担或误导后续修改

输出：

- 可晋升候选（建议进入规则）
- 可提取候选（建议生成技能）
- 待删除或待合并条目（降噪）

### 2) Promote：规则晋升

准入标准（全部满足）：

- 至少 2 次真实场景验证
- 能写成明确应当/禁止语句
- 与现有规则不冲突，或已合并冲突条目

落地要求：

- 使用简洁、可执行语言
- 每条规则只表达一个核心约束
- 添加最小必要示例，避免长篇解释

### 3) Extract：技能提取

当某方案具备可复用步骤、明确输入输出、常见陷阱时，提取为独立技能：

- 必备结构
  - `SKILL.md`：用途、触发条件、步骤、验收标准
  - `references/`：关键背景资料或链接
  - `examples/`：至少 1 个正例和 1 个边界例

### 4) Remember：显式记忆写入

仅在以下情况写入：

- 该信息会显著提升后续任务成功率
- 该信息短期内会被频繁复用
- 当前规则层尚未覆盖此知识点

## 决策矩阵

同一条经验应放在哪里：

- 放规则文件：稳定、通用、必须遵守
- 放技能：步骤化、可迁移、可复用的解决方案
- 放临时记忆：尚在观察期，证据不足

## 质量门禁（执行后自检）

每次执行本技能后，至少确认：

- 新增规则是否与现有规则重复或冲突
- 提取出的技能是否可被第三方直接理解并复现
- 记忆清理是否误删仍在使用的上下文
- 是否保留必要证据（命令结果、错误特征、验证方式）

## 输出模板（建议）

### A. Review 报告

- 候选晋升规则（含理由）
- 候选提取技能（含收益）
- 待清理条目（含风险提示）

### B. Promote 结果

- 新增/更新规则列表
- 冲突处理说明
- 验证结果（lint/test/build）

### C. Extract 结果

- 技能目录结构
- 核心步骤摘要
- 示例与边界说明

## 迁移说明（从 Claude Code 版本到 Cursor）

- 不再依赖 `/si:*` 指令体系
- 不再依赖 Claude 插件安装流程
- 保留原有 review/promote/extract/remember 能力，但改为 Cursor Agent 的任务步骤与产物约束

## 反模式（避免）

- 把一次性 bug workaround 直接写成长期规则
- 将风格偏好伪装成工程约束
- 技能文档缺少输入输出，导致不可复现
- 只记录结论，不保留验证证据

## 最小执行清单

- [ ] 完成一次 review，产出候选列表
- [ ] 至少晋升 1 条高价值规则（如存在）
- [ ] 至少提取 1 个可复用技能（如存在）
- [ ] 清理重复/过期记忆，记录清理原因
- [ ] 补充验证证据并归档
---
name: "self-improving-agent"
description: "Curate Claude Code's auto-memory into durable project knowledge. Analyze MEMORY.md for patterns, promote proven learnings to CLAUDE.md and .claude/rules/, extract recurring solutions into reusable skills. Use when: (1) reviewing what Claude has learned about your project, (2) graduating a pattern from notes to enforced rules, (3) turning a debugging solution into a skill, (4) checking memory health and capacity."
---

# Self-Improving Agent

> Auto-memory captures. This plugin curates.

Claude Code's auto-memory (v2.1.32+) automatically records project patterns, debugging insights, and your preferences in `MEMORY.md`. This plugin adds the intelligence layer: it analyzes what Claude has learned, promotes proven patterns into project rules, and extracts recurring solutions into reusable skills.

## Quick Reference

| Command | What it does |
|---------|-------------|
| `/si:review` | Analyze MEMORY.md — find promotion candidates, stale entries, consolidation opportunities |
| `/si:promote` | Graduate a pattern from MEMORY.md → CLAUDE.md or `.claude/rules/` |
| `/si:extract` | Turn a proven pattern into a standalone skill |
| `/si:status` | Memory health dashboard — line counts, topic files, recommendations |
| `/si:remember` | Explicitly save important knowledge to auto-memory |

## How It Fits Together

```
┌─────────────────────────────────────────────────────────┐
│                  Claude Code Memory Stack                │
├─────────────┬──────────────────┬────────────────────────┤
│  CLAUDE.md  │   Auto Memory    │   Session Memory       │
│  (you write)│   (Claude writes)│   (Claude writes)      │
│  Rules &    │   MEMORY.md      │   Conversation logs    │
│  standards  │   + topic files  │   + continuity         │
│  Full load  │   First 200 lines│   Contextual load      │
├─────────────┴──────────────────┴────────────────────────┤
│              ↑ /si:promote        ↑ /si:review          │
│         Self-Improving Agent (this plugin)               │
│              ↓ /si:extract    ↓ /si:remember            │
├─────────────────────────────────────────────────────────┤
│  .claude/rules/    │    New Skills    │   Error Logs     │
│  (scoped rules)    │    (extracted)   │   (auto-captured)│
└─────────────────────────────────────────────────────────┘
```

## Installation

### Claude Code (Plugin)
```
/plugin marketplace add alirezarezvani/claude-skills
/plugin install self-improving-agent@claude-code-skills
```

### OpenClaw
```bash
clawhub install self-improving-agent
```

### Codex CLI
```bash
./scripts/codex-install.sh --skill self-improving-agent
```

## Memory Architecture

### Where things live

| File | Who writes | Scope | Loaded |
|------|-----------|-------|--------|
| `./.cursorrules` | You (+ promote step) | Project rules | Full file, every session |
| `./.cursor/rules/*.md` | You (+ promote step) | Scoped rules | When matching files are in context |
| `./.agents/skills/**/SKILL.md` | You/Agent (extract step) | Reusable workflows | On demand when skill is invoked |
| Session context (Cursor Agent) | Agent runtime | Temporary learnings | Current conversation only |
| `./docs/knowledge/*.md` (optional) | You/Agent | Team-shared durable notes | On demand |

### The promotion lifecycle

```
1. Claude discovers pattern → auto-memory (MEMORY.md)
2. Pattern recurs 2-3x → /si:review flags it as promotion candidate
3. You approve → /si:promote graduates it to CLAUDE.md or rules/
4. Pattern becomes an enforced rule, not just a note
5. MEMORY.md entry removed → frees space for new learnings
```

## Core Concepts

### Auto-memory is capture, not curation

Auto-memory is excellent at recording what Claude learns. But it has no judgment about:
- Which learnings are temporary vs. permanent
- Which patterns should become enforced rules
- When the 200-line limit is wasting space on stale entries
- Which solutions are good enough to become reusable skills

That's what this plugin does.

### Promotion = graduation

When you promote a learning, it moves from Claude's scratchpad (MEMORY.md) to your project's rule system (CLAUDE.md or `.claude/rules/`). The difference matters:

- **MEMORY.md**: "I noticed this project uses pnpm" (background context)
- **CLAUDE.md**: "Use pnpm, not npm" (enforced instruction)

Promoted rules have higher priority and load in full (not truncated at 200 lines).

### Rules directory for scoped knowledge

Not everything belongs in CLAUDE.md. Use `.claude/rules/` for patterns that only apply to specific file types:

```yaml
# .claude/rules/api-testing.md
---
paths:
  - "src/api/**/*.test.ts"
  - "tests/api/**/*"
---
- Use supertest for API endpoint testing
- Mock external services with msw
- Always test error responses, not just happy paths
```

This loads only when Claude works with API test files — zero overhead otherwise.

## Agents

### memory-analyst
Analyzes MEMORY.md and topic files to identify:
- Entries that recur across sessions (promotion candidates)
- Stale entries referencing deleted files or old patterns
- Related entries that should be consolidated
- Gaps between what MEMORY.md knows and what CLAUDE.md enforces

### skill-extractor
Takes a proven pattern and generates a complete skill:
- SKILL.md with proper frontmatter
- Reference documentation
- Examples and edge cases
- Ready for `/plugin install` or `clawhub publish`

## Hooks

### error-capture (PostToolUse → Bash)
Monitors command output for errors. When detected, appends a structured entry to auto-memory with:
- The command that failed
- Error output (truncated)
- Timestamp and context
- Suggested category

**Token overhead:** Zero on success. ~30 tokens only when an error is detected.

## Platform Support

| Platform | Memory System | Plugin Works? |
|----------|--------------|---------------|
| Claude Code | Auto-memory (MEMORY.md) | ✅ Full support |
| OpenClaw | workspace/MEMORY.md | ✅ Adapted (reads workspace memory) |
| Codex CLI | AGENTS.md | ✅ Adapted (reads AGENTS.md patterns) |
| GitHub Copilot | `.github/copilot-instructions.md` | ⚠️ Manual promotion only |

## Related

- [Claude Code Memory Docs](https://code.claude.com/docs/en/memory)
- [pskoett/self-improving-agent](https://clawhub.ai/pskoett/self-improving-agent) — inspiration
- [playwright-pro](../playwright-pro/) — sister plugin in this repo
