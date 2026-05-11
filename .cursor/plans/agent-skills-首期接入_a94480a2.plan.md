---
name: agent-skills-首期接入
overview: 在聊天主链路中引入按需加载的 Agent Skills（目录发现 + load_skill 执行），并新增前端“网站构建”开关；开关开启时自动启用网站构建相关 skills 与沙箱文件工具。
todos:
  - id: schema-and-frontend-flag
    content: 新增 websiteBuildMode 字段并打通前后端请求透传
    status: pending
  - id: skill-registry-and-docs
    content: 实现 skill 目录发现与按需 load_skill，并补齐前后端代码生成 SKILL.md
    status: pending
  - id: agent-skills-mcp
    content: 实现 agent-skills-mcp（load_skill + 沙箱文件工具）并注册到 MCPRegistry
    status: pending
  - id: chat-session-integration
    content: 在 ChatSessionAgent/prompt 中按网站构建开关注入技能目录与工具
    status: pending
  - id: tests-and-validation
    content: 补充后端单测与前端行为校验，完成联调验收
    status: pending
isProject: false
---

# Agent Skills 首期落地方案

## 目标与范围
- 对齐你确认的方向：采用 `s05` 模式（先注入 skills 目录，再按需 `load_skill`）；新增前端“网站构建”开关。
- 首期仅覆盖“前后端代码生成”场景，不扩展到通用任务编排。
- 文件工具限定为沙箱目录（不直接操作业务仓库）。

## 后端改造
- 在请求模型中增加网站构建开关字段，贯通到会话执行链路：
  - [backend/app/schemas/chat.py](backend/app/schemas/chat.py)
  - [backend/app/agents/chat_session_agent.py](backend/app/agents/chat_session_agent.py)
- 新增 skills 注册与加载模块（轻量目录 + 按需正文）：
  - [backend/app/services/chat/agent_skills/registry.py](backend/app/services/chat/agent_skills/registry.py)
  - [backend/app/services/chat/agent_skills/models.py](backend/app/services/chat/agent_skills/models.py)
  - 首期 skills 文档：`frontend-codegen`、`backend-codegen`（放在 `backend/app/services/chat/agent_skills/skills/*/SKILL.md`）
- 新增本地 MCP server（建议命名 `agent-skills-mcp`），提供：
  - `load_skill(name)`：返回 skill 正文
  - `list_workspace_files(path?)` / `read_workspace_file(path)` / `write_workspace_file(path, content)` / `delete_workspace_file(path)`：仅允许访问沙箱根目录
  - 相关文件：
    - [backend/app/mcp/mcp_registry.py](backend/app/mcp/mcp_registry.py)
    - [backend/app/mcp/mcp_servers/agent_skills_mcp/server.py](backend/app/mcp/mcp_servers/agent_skills_mcp/server.py)
    - [backend/app/mcp/mcp_servers/agent_skills_mcp/config.py](backend/app/mcp/mcp_servers/agent_skills_mcp/config.py)
- 在会话 prompt 里注入 skills 目录（仅网站构建模式生效），并约束调用顺序：先 `load_skill` 再执行代码/文件工具。
  - [backend/app/prompts/system_prompt.py](backend/app/prompts/system_prompt.py)
  - [backend/app/prompts/prompt_utils.py](backend/app/prompts/prompt_utils.py)

## 前端改造
- 在输入配置中新增 `websiteBuildMode`（布尔），本地缓存与请求透传都纳入：
  - [frontend/src/interfaces/chat.ts](frontend/src/interfaces/chat.ts)
  - [frontend/src/pages/ChatPage/components/ChatInput/constant.ts](frontend/src/pages/ChatPage/components/ChatInput/constant.ts)
  - [frontend/src/pages/ChatPage/components/ChatInput/hooks.ts](frontend/src/pages/ChatPage/components/ChatInput/hooks.ts)
- 在输入区底部将“网站构建”开关放在 `ChatInputFooter`，与“深度思考”并列展示。
  - [frontend/src/pages/ChatPage/components/ChatInput/components/ChatInputFooter.tsx](frontend/src/pages/ChatPage/components/ChatInput/components/ChatInputFooter.tsx)

## 执行链路（首期）
```mermaid
flowchart TD
userReq[UserRequest] --> chatReq[ChatRequest.websiteBuildMode]
chatReq --> chatAgent[ChatSessionAgent]
chatAgent --> sysPrompt[SystemPrompt_withSkillManifest]
chatAgent --> tools[ToolList_MCP_plus_AgentSkills]
llm[LLM] -->|call load_skill| skillsMcp[agent-skills-mcp]
skillsMcp --> llm
llm -->|call sandbox_file_tools| skillsMcp
llm --> finalAnswer[FinalResponse]
```

## 验证与验收
- 后端：新增单测覆盖 skill 注册/加载、沙箱路径越权拦截、文件工具 CRUD。
- 前端：开关状态持久化、请求体包含 `website_build_mode`、关闭时不注入 skills。
- 联调：网站构建开关开启后，观察工具流中先出现 `load_skill`，再出现代码/文件工具调用。

## 风险与兜底
- 路径安全：所有文件工具必须做 `resolve()` + 沙箱根路径前缀校验，拒绝 `..` 越权。
- 上下文膨胀：`load_skill` 返回正文长度设置上限，必要时截断并附提示。
- 工具误用：网站构建开关关闭时，不向模型暴露 skills/file 工具。
