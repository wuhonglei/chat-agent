# React 前端项目依赖分析与 Cursor Agent Skills 推荐

## 一、项目依赖分析 (package.json)

### 1. 核心技术栈

| 类别 | 依赖 | 版本 | 用途 |
|------|------|------|------|
| **框架** | react | ^19.2.3 | 核心 UI 框架 |
| | react-dom | ^19.2.3 | React DOM 渲染 |
| **构建** | vite | ^7.3.1 | 构建与开发服务器 |
| **路由** | react-router-dom | ^7.11.0 | 前端路由 |
| **状态** | @reduxjs/toolkit | ^2.11.2 | Redux 状态管理 |
| | react-redux | ^9.2.0 | React-Redux 绑定 |
| **UI** | antd | ^6.1.4 | Ant Design 组件库 |
| | @ant-design/icons | ^6.1.0 | 图标 |
| | @ant-design/x | ^2.1.3 | 扩展组件（如 Upload） |
| | @ant-design/x-markdown | ^2.1.3 | Markdown 渲染 |
| **样式** | tailwindcss | ^4.1.18 | 原子化 CSS |
| | @tailwindcss/postcss / vite / typography | 配套 | Tailwind 集成 |
| **语言** | typescript | ^5.9.3 | 类型系统 |

### 2. 业务与数据相关

| 依赖 | 版本 | 用途 |
|------|------|------|
| axios | ^1.13.2 | HTTP 请求 |
| @microsoft/fetch-event-source | ^2.0.1 | SSE 流式请求（如 AI 对话流） |
| dexie | ^4.2.1 | IndexedDB 封装（本地存储） |
| jwt-decode | ^4.0.0 | JWT 解析 |
| camelcase-keys / snakecase-keys | ^10.0.1 / ^9.0.2 | 驼峰/下划线转换 |
| ajv / ajv-formats | ^8.17.1 / ^3.0.1 | JSON Schema 校验 |
| uuid | ^13.0.0 | 唯一 ID |

### 3. UI 增强与富文本

| 依赖 | 版本 | 用途 |
|------|------|------|
| react-syntax-highlighter | ^16.1.0 | 代码高亮 |
| highlight.js | ^11.11.1 | 语法高亮引擎 |
| simplebar-react | ^3.3.2 | 自定义滚动条 |
| antd-img-crop | ^4.27.0 | 图片裁剪（头像等） |
| react-error-boundary | ^6.0.2 | 错误边界 |
| classnames | ^2.5.1 | 条件 class 拼接 |

### 4. 工具与工具链

| 依赖 | 版本 | 用途 |
|------|------|------|
| ahooks | ^3.9.6 | React Hooks 工具库 |
| dayjs | ^1.11.19 | 日期处理 |
| lodash-es | ^4.17.22 | 工具函数 |
| mitt | ^3.0.1 | 事件总线 |
| jsonrepair | ^3.13.1 | 破损 JSON 修复 |
| aegis-web-sdk | ^1.41.10 | 前端监控/埋点 |

### 5. 开发依赖 (devDependencies)

| 依赖 | 用途 |
|------|------|
| @vitejs/plugin-react | Vite + React |
| vite-plugin-svgr | SVG 作为 React 组件 |
| eslint + @typescript-eslint/* | 代码检查 |
| prettier | 代码格式化 |
| husky + lint-staged | Git 提交前 lint/format |
| typescript-json-schema | 从 TS 生成 JSON Schema |

### 6. 技术栈小结

- **构建**: Vite 7 + TypeScript 5
- **UI**: React 19 + Ant Design 6 + Tailwind 4
- **状态/数据**: Redux Toolkit + React-Redux + Dexie(IndexedDB)
- **网络**: Axios + fetch-event-source（流式）
- **工程**: ESLint + Prettier + Husky + lint-staged

---

## 二、SkillsMP 与 Cursor Agent Skills 简介

### SkillsMP (https://skillsmp.com/skills)

- **平台**: 面向 Claude、Codex、Cursor 的 Agent Skills 市场，基于 **SKILL.md** 开放标准。
- **规模**: 约 **91,908+** 个技能，支持语义搜索、分类、按人气/最近更新排序。
- **安装**: 从 GitHub 克隆对应仓库，将技能目录放到 Cursor 的 skills 路径即可，Cursor 会自动发现并加载。

### Cursor 中 Skills 的加载路径

| 路径 | 作用域 |
|------|--------|
| `.cursor/skills/` | 项目级 |
| `~/.cursor/skills/` | 用户级（全局） |

> 也兼容 `.claude/skills/`、`.codex/skills/`。每个技能至少需要 `SKILL.md`，可搭配 `scripts/`、`references/`、`assets/` 等。

---

## 三、适合本项目的 Cursor Agent Skills 推荐

结合 **React + Vite + Ant Design + Redux + TypeScript** 技术栈，从 [SkillsMP](https://skillsmp.com/skills) 挑选了以下可直接或间接使用的技能（均可在 SkillsMP 或对应 GitHub 找到）。

### 高相关度（直接对应技术栈）

| 技能 | 来源 | 适用场景 | 链接 |
|------|------|----------|------|
| **fix** | facebook/react | 修复 lint、格式化问题，提交前检查 | [SkillsMP - fix](https://skillsmp.com/skills/facebook-react-claude-skills-fix-skill-md) |
| **extract-errors** | facebook/react | 新增/处理 React 错误信息、“unknown error code” | [SkillsMP - extract-errors](https://skillsmp.com/skills/facebook-react-claude-skills-extract-errors-skill-md) |
| **flow** | facebook/react | 若引入 Flow 做类型检查时的使用方式 | [SkillsMP - flow](https://skillsmp.com/skills/facebook-react-claude-skills-flow-skill-md) |
| **test** | facebook/react | 运行 React 相关测试（你项目若用 Jest/Vitest 可参考思路） | [SkillsMP - test](https://skillsmp.com/skills/facebook-react-claude-skills-test-skill-md) |
| **vercel-react-best-practices** | langgenius/dify | React/Next 性能、组件、数据获取、bundle 优化；Vite 项目也可借鉴 | [SkillsMP - vercel-react-best-practices](https://skillsmp.com/skills/langgenius-dify-agents-skills-vercel-react-best-practices-skill-md) |
| **web-design-guidelines** | langgenius/dify | UI 审查、可访问性、设计/UX 自查 | [SkillsMP - web-design-guidelines](https://skillsmp.com/skills/langgenius-dify-agents-skills-web-design-guidelines-skill-md) |

### 通用开发与协作

| 技能 | 来源 | 适用场景 | 链接 |
|------|------|----------|------|
| **skill-lookup** | f/awesome-chatgpt-prompts | 查找、安装、检索 Agent Skills | [SkillsMP - skill-lookup](https://skillsmp.com/skills/f-awesome-chatgpt-prompts-plugins-claude-prompts-chat-skills-skill-lookup-skill-md) |
| **create-pr** | n8n-io/n8n | 按规范创建 GitHub PR，包含标题格式 | [SkillsMP - create-pr](https://skillsmp.com/skills/n8n-io-n8n-claude-skills-create-pr-skill-md) |
| **verify** | facebook/react | 提交前完整校验（lint、测试、构建等） | [SkillsMP - verify](https://skillsmp.com/skills/facebook-react-claude-skills-verify-skill-md) |

### 与 Vite / 前端工程相关（通过 Development / Tools 分类筛选）

| 技能 | 来源 | 适用场景 |
|------|------|----------|
| **playwright-cli** | microsoft/playwright | 自动化浏览器测试、表单、截图、爬取（E2E） |
| **browser-use** | browser-use/browser-use | 浏览器自动化、页面交互、测试 |
| **skill-creator** | langgenius/dify 或 google-gemini/gemini-cli | 学习如何为 Cursor/Claude 编写自定义 Skill |
| **mcp-integration** | anthropics/claude-code | 若需要接入 MCP（Model Context Protocol）做工具/服务集成 |

### SkillsMP 分类入口（便于你后续自行扩展）

- **Development**（前端/全栈）: https://skillsmp.com/categories/development  
- **Tools**（CLI、自动化、效率）: https://skillsmp.com/categories/tools  
- **Testing & Security**: https://skillsmp.com/categories/testing-security  
- **Documentation**: https://skillsmp.com/categories/documentation  

---

## 四、安装与使用方式

### 1. 从 SkillsMP 获取技能

1. 打开 [SkillsMP - skills](https://skillsmp.com/skills)。
2. 搜索或按分类找到技能（如 `fix`、`vercel-react-best-practices`）。
3. 在技能详情中查看 **GitHub 仓库** 和 **SKILL.md 路径**。
4. 克隆仓库或下载对应目录，放到 Cursor 的 skills 路径。

### 2. 项目级安装示例

```bash
# 在项目根目录
mkdir -p .cursor/skills

# 示例：从 facebook/react 的 claude-skills 中取 fix
# 需根据该仓库实际结构拷贝 fix 技能目录到 .cursor/skills/fix
```

### 3. 用户级安装（多项目复用）

```bash
mkdir -p ~/.cursor/skills
# 将技能目录放入 ~/.cursor/skills/<skill-name>/
```

### 4. 使用 `npx skills add`（推荐）

[skills](https://www.npmjs.com/package/skills) CLI 支持从 GitHub 仓库安装，并自动配置 Cursor 等 agent：

```bash
# 语法
npx skills add <source> -s <skill_name> [-s <skill_name> ...] -a cursor -y

# 列出某仓库中的可选技能
npx skills add <source> -l

# 示例：安装 vercel-labs 的 React 最佳实践、Web 设计规范
npx skills add vercel-labs/agent-skills -s vercel-react-best-practices -s web-design-guidelines -a cursor -y

# 示例：安装 anthropics 的 frontend-design、skill-creator、webapp-testing
npx skills add anthropics/skills -s frontend-design -s skill-creator -s webapp-testing -a cursor -y
```

- **source**：GitHub 简写 `owner/repo`、Git URL 或本地路径
- **-s, --skill**：要安装的技能名（可多次，否则会进入交互选择）
- **-a, --agent**：目标 agent，如 `cursor`
- **-y**：跳过确认
- **-l, --list**：只列出技能，不安装

安装后技能会出现在 `.agents/skills/`，并按 agent 做 symlink；Cursor 会从该目录加载。

### 5. 使用 OpenSkills（若采用）

```bash
npm i -g openskills
openskills install anthropics/skills   # 或其他 SkillsMP 上标注支持的仓库
openskills sync                        # 若项目有 AGENTS.md
```

> 部分技能来自 Anthropic/Claude Code，OpenSkills 可能更适配；SkillsMP 上的技能多数需按 GitHub 说明手动拷贝到 `.cursor/skills/` 或 `~/.cursor/skills/`。

---

## 五、简要对照：依赖 ↔ 推荐技能

| 你的依赖/场景 | 可搭配的 Agent Skill |
|----------------|----------------------|
| React 19 + antd | fix, extract-errors, vercel-react-best-practices, web-design-guidelines |
| Redux Toolkit | vercel-react-best-practices（状态与性能）、test（测试思路） |
| Vite + TypeScript | fix, verify, skill-creator（若自定义 Vite/TS 相关技能） |
| Ant Design | web-design-guidelines（UI/可访问性） |
| ESLint + Prettier | fix, verify |
| SSE/流式请求、AI 对话 | 可在 Data & AI 分类中查找 LLM/流式相关技能 |
| E2E/浏览器测试 | playwright-cli, browser-use |

---

## 六、参考链接

- **SkillsMP 首页**: https://skillsmp.com  
- **SkillsMP 技能列表**: https://skillsmp.com/skills  
- **SkillsMP 分类**: https://skillsmp.com/categories  
- **Cursor - Agent Skills 文档**: https://cursor.com/docs/context/skills  
- **Anthropic - Building skills for Claude Code**: https://www.claude.com/blog/building-skills-for-claude-code  

---

*文档基于当前 `package.json` 与 SkillsMP 公开信息整理，技能链接与分类以 SkillsMP 为准，请以官网最新结构为准进行安装。*
