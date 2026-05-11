---
name: agent-skills-workspace-隔离改造
overview: 将 Agent Skills 沙箱目录从 per_user 单 workspace 升级为 per_user+conversation 工作区隔离，使用 conversation_id 作为 workspace_id，并移除历史数据兼容逻辑。
todos:
  - id: pass-conversation-as-workspace
    content: 在 ChatSessionAgent -> MCPToolSession -> ToolExecutor 链路传递 workspace_id=conversation_id
    status: pending
  - id: inject-workspace-id
    content: 在 ToolExecutor 对 agent-skills 工作区工具强制注入 user_id 和 workspace_id
    status: pending
  - id: workspace-path-refactor
    content: 重构 agent_skills_mcp utils/server 使用 workspaces/<workspace_id> 新路径且不做历史兼容
    status: pending
  - id: tests-and-doc-sync
    content: 补充隔离与校验测试，并同步计划文档中的路径与策略说明
    status: pending
isProject: false
---

# Agent Skills 工作区隔离改造计划

## 目标

- 将沙箱根路径从 `backend/data/user_data/<user_id>/workspace/` 调整为 `backend/data/user_data/<user_id>/workspaces/<workspace_id>/`。
- `workspace_id` 固定使用 `conversation_id`，确保同一用户不同会话文件互不覆盖。
- 不做历史路径兼容与自动迁移，严格仅使用新路径。

## 影响范围

- 会话编排层：注入 `conversation_id` 到工具执行上下文。
- MCP 工具执行层：为 agent-skills 工具统一注入 `workspace_id`。
- agent-skills-mcp 工具层：所有文件与 bash 工具基于新目录解析。
- 文档/计划：同步更新路径说明，避免误导。

关键文件：

- [backend/app/agents/chat_session_agent.py](backend/app/agents/chat_session_agent.py)
- [backend/app/agents/mcp_tool_execution.py](backend/app/agents/mcp_tool_execution.py)
- [backend/app/agents/tool_executor.py](backend/app/agents/tool_executor.py)
- [backend/app/mcp/mcp_servers/agent_skills_mcp/utils.py](backend/app/mcp/mcp_servers/agent_skills_mcp/utils.py)
- [backend/app/mcp/mcp_servers/agent_skills_mcp/server.py](backend/app/mcp/mcp_servers/agent_skills_mcp/server.py)
- `[.cursor/plans/agent-skills-首期接入_a94480a2.plan.md](.cursor/plans/agent-skills-首期接入_a94480a2.plan.md)`

## 实施步骤

1. 扩展请求上下文传递 `workspace_id`

- 在 [backend/app/agents/chat_session_agent.py](backend/app/agents/chat_session_agent.py) 中，移除当前对 `conversation_id` 的丢弃逻辑（现状是 `_ = conversation_id`），将 `conversation_id` 传入 `MCPToolSession.reset_for_request(...)`。
- 在 [backend/app/agents/mcp_tool_execution.py](backend/app/agents/mcp_tool_execution.py) 为 `reset_for_request` 增加 `workspace_id` 参数，并透传给执行器。

1. 在工具执行器中强制注入 `workspace_id`

- 在 [backend/app/agents/tool_executor.py](backend/app/agents/tool_executor.py) 的请求级状态中新增 `current_workspace_id`。
- 扩展 `_inject_user_id_for_agent_skills(...)` 为统一注入 `user_id` + `workspace_id`（仅限 agent-skills 工作区工具）。
- 约束：永远覆盖模型侧同名参数，避免越权或跨会话写入。

1. 重构工作区路径解析到新目录结构

- 在 [backend/app/mcp/mcp_servers/agent_skills_mcp/utils.py](backend/app/mcp/mcp_servers/agent_skills_mcp/utils.py)：
  - 新增/扩展 `validate_workspace_id(workspace_id: str)`（与 `user_id` 同等级安全校验）。
  - 将 `get_workspace_root(user_id)` 改为 `get_workspace_root(user_id, workspace_id)`，返回 `.../workspaces/<workspace_id>`。
  - 将 `resolve_workspace_path(...)` 改为接收 `workspace_id` 并基于新 root 解析。
- 不添加旧 `workspace/` 回退逻辑。

1. 调整 MCP 工具签名与调用

- 在 [backend/app/mcp/mcp_servers/agent_skills_mcp/server.py](backend/app/mcp/mcp_servers/agent_skills_mcp/server.py) 中，以下工具新增必填参数 `workspace_id`：
  - `list_workspace_files`
  - `read_workspace_file`
  - `write_workspace_file`
  - `delete_workspace_file`
  - `clear_workspace`
  - `run_bash`
- 工具内部统一调用新签名的 `resolve_workspace_path/get_workspace_root`。

1. 同步计划文档与运行约定

- 更新 `[.cursor/plans/agent-skills-首期接入_a94480a2.plan.md](.cursor/plans/agent-skills-首期接入_a94480a2.plan.md)` 中的沙箱路径描述与隔离策略，明确为 `per_user + per_conversation`。
- 明确“无历史兼容”的行为预期（旧路径数据不可见）。

## 验证与验收

- 单元测试建议覆盖：
  - 同一 `user_id` 下，不同 `workspace_id(conversation_id)` 写同名文件，互不影响。
  - 省略/非法 `workspace_id` 时，agent-skills 工作区工具报错。
  - 路径越权防护（`..`、绝对路径、敏感段）在新目录下仍生效。
- 集成验证：
  - 开启网站构建模式，连续两个会话分别生成同名项目目录，确认各自仅出现在对应 `workspaces/<conversation_id>/` 下。

## 风险与注意事项

- 旧目录无兼容会导致历史会话产物不可见，属于预期行为，需在发布说明中明确。
- `run_bash` 工作目录切换到新会话级路径后，脚本/命令依赖的相对路径语义会变化，需通过回归测试确认。
