# Agent 模式开关改造计划

> 文档状态：历史改造计划 + 当前实现差异说明。下方“需求总结/执行顺序”保留当时改造背景，不应作为现网行为的唯一依据。

## 当前实现摘要（2026-06）

- 请求字段仍为 `agent_mode: int`，`0` 表示普通对话，`>0` 表示 Agent 模式。
- MCP Server 暴露列表由 `backend/app/schemas/config.py` 的 `normal_mode_servers` 与 `agent_mode_servers` 控制；默认 Agent 模式包含 `file`、`skill_manager`、`shell`、`tavily`、`context7`、`zread`，并非只启用 file/shell。
- Agent 模式系统提示词使用 `<skill_system>` 与 `<working_directory>`，虚拟目录包括 `/mnt/user-data/workspace/`、`/mnt/user-data/uploads/`、`/mnt/user-data/outputs/`、`/mnt/skills/public/`、`/mnt/skills/custom/`。
- 上传附件在普通模式走 RAG：后端构建 `<attachment_context>` 注入检索片段。
- 上传附件在 Agent 模式不走 RAG：后端构建 `<attachment_uploads>` 清单，列出本会话上传文件的 `name/type/virtual_path/size/uploaded_this_turn`；PDF / Excel 额外提供派生 Markdown 的 `virtual_path`，供模型用 file MCP 按需读取。
- 附件虚拟路径来自 `storage_key` 的会话相对部分：`{conversation_id}/report.pdf` 对应 `/mnt/user-data/uploads/report.pdf`，`{conversation_id}/derived/report.md` 对应 `/mnt/user-data/uploads/derived/report.md`。

## 一、需求总结

| 项目 | 当前值 | 目标值 |
|------|--------|--------|
| 开关文案 | "网站构建" | "Agent" |
| 图标 | WebSiteIcon | AgentIcon |
| 字段名 | websiteBuildMode | agentMode |
| 字段类型 | boolean | number (0=关闭, 1=开启) |
| file_mcp/shell_mcp | 始终启用 | 仅在 agent_mode=1 时启用 |
| 最大迭代次数 | sys.maxsize (无限) | 20 轮 |

---

## 二、前端修改（6个文件）

### 1. 类型定义

**文件**: `frontend/src/interfaces/chat.ts`

```typescript
// 第 61-65 行
export interface ChatInputConfig {
  thinkMode: boolean;
  agentMode: number;  // 0=关闭, 1=开启
  modelID: string;
}
```

### 2. 表单字段名常量

**文件**: `frontend/src/pages/ChatPage/components/ChatInput/constant.ts`

```typescript
// 第 6 行
agentMode: ["agentMode"] as NamePath,
```

### 3. 默认值和持久化

**文件**: `frontend/src/pages/ChatPage/components/ChatInput/hooks.ts`

```typescript
// 第 44-48 行
const defaultFormValue: ChatInputConfig = {
  thinkMode: false,
  agentMode: 0,
  modelID: "default",
};
```

### 4. UI 组件

**文件**: `frontend/src/pages/ChatPage/components/ChatInput/components/ChatInputFooter.tsx`

```tsx
// 第 1-3 行 - 修改导入
import AgentIcon from "@/assets/svg/AgentIcon.svg?react";
// 删除 WebSiteIcon 导入

// 第 55-64 行 - 修改开关按钮
<Form.Item trigger="onClick" initialValue={0} valuePropName="active" name={names.agentMode}>
  <CustomButton
    size={size}
    bordered={false}
    icon={<AgentIcon />}
    tooltip={isSmallScreen ? undefined : "启用 Agent 模式"}
  >
    {isSmallScreen ? "" : "Agent"}
  </CustomButton>
</Form.Item>
```

### 5. 欢迎页联动

**文件**: `frontend/src/pages/WelcomePage/index.tsx`

```typescript
// 第 64 行
const agentMode = Form.useWatch("agentMode", form);

// 第 98 行
{agentMode ? (
  // ... 欢迎提示卡片
) : null}
```

### 6. 消息元数据

**文件**: `frontend/src/utils/chat.ts`

无需修改，因为该文件使用的是 `ChatInputFormValues` 类型，字段名变更会自动传播。

---

## 三、后端修改（4个文件）

### 1. ChatRequest Schema

**文件**: `backend/app/schemas/chat.py`

```python
# 第 106-108 行
agent_mode: int = Field(
    0, description="Agent mode: 0=disabled, 1=enabled"
)
```

### 2. 核心逻辑

**文件**: `backend/app/agents/chat_session_agent.py`

**修改点 1：技能清单注入**（第 106-110 行）
```python
skill_manifests = (
    skill_registry.list_manifests(allowed_names=DEFAULT_ALLOWED_SKILL_NAMES)
    if chat_request.agent_mode > 0
    else []
)
```

**修改点 2：系统提示词注入**（第 111-116 行）
```python
system_prompt = get_system_prompt_for_chat_session(
    agent_mode=chat_request.agent_mode,
    skill_manifests=skill_manifests,
    user_id=user_id,
    workspace_id=conversation_id,
)
```

**修改点 3：工具迭代次数限制**（第 163-172 行）
```python
AGENT_MODE_MAX_ITERATIONS = 20

max_iterations_by_tool = (
    AGENT_MODE_MAX_ITERATIONS
    if chat_request.agent_mode > 0
    else tool_session.MAX_ITERATIONS_BY_TOOL
)
max_total_iterations = (
    AGENT_MODE_MAX_ITERATIONS
    if chat_request.agent_mode > 0
    else tool_session.MAX_TOTAL_ITERATIONS
)
```

**修改点 4：MCP 服务器暴露列表**（当前实现见 `backend/app/schemas/config.py`）
```python
normal_mode_servers = ["time", "weather", "tavily", "code", "context7", "zread"]
agent_mode_servers = ["file", "skill_manager", "shell", "tavily", "context7", "zread"]
```

### 3. 系统提示词模板

**文件**: `backend/app/prompts/system_prompt.py`

```python
{%- if agent_mode > 0 %}
<skill_system>
内置技能：`{{ skills_public_prefix.rstrip('/') }}/`
用户自定义技能：`{{ skills_custom_prefix.rstrip('/') }}`
<available_skills>
{%- for skill in skill_manifests %}
  <skill>
    <name>{{ skill.name }}</name>
    <description>{{ skill.description }}</description>
    <location>{{ skill.location }}</location>
  </skill>
{%- endfor %}
</available_skills>
</skill_system>

<working_directory existed="true">
- 用户上传：`{{ uploads_prefix.rstrip('/') }}`
- 用户工作区：`{{ workspace_prefix.rstrip('/') }}`
- 输出文件：`{{ outputs_prefix.rstrip('/') }}`
</working_directory>
{%- endif %}
```

### 4. 提示词工具函数

**文件**: `backend/app/prompts/prompt_utils.py`

```python
def get_system_prompt_for_chat_session(
    *,
    agent_mode: int = 0,
    skill_manifests: Sequence[AgentSkillManifest] | None = None,
) -> str:
    """Get system prompt for final response generation."""
    extra = _get_agent_mode_prompt_context() if agent_mode > 0 else {}
    return system_prompt_for_chat_session_template.render(
        agent_mode=agent_mode,
        skill_manifests=skill_manifests or [],
        **extra,
    )
```

---

## 四、变更影响分析

| 影响点 | 说明 |
|--------|------|
| localStorage 兼容性 | 字段名从 `websiteBuildMode` 改为 `agentMode`，类型从 boolean 改为 number。旧数据会被忽略，使用新默认值 `0` |
| 消息元数据 | 存储在 `message_metadata` JSON 字段中，无需数据库迁移 |
| API 兼容性 | 前端发送 `agent_mode: 0/1`，后端接收 `agent_mode: int` |
| MCP 服务器 | Agent 模式暴露列表由 `agent_mode_servers` 配置控制；默认包含 file / skill_manager / shell / tavily / context7 / zread |
| 附件上下文 | 普通模式使用附件 RAG；Agent 模式注入 `<attachment_uploads>` 并由模型按需读取虚拟路径 |

---

## 五、验证清单

### 前端验证
- [ ] 开关显示 "Agent" 文案和 AgentIcon 图标
- [ ] 点击开关切换值在 0/1 之间
- [ ] 开关状态持久化到 localStorage
- [ ] 欢迎页根据 agentMode 显示/隐藏提示卡片

### 后端验证
- [ ] Agent 模式下，系统提示词包含 `<skill_system>` 与 `<working_directory>` 块
- [ ] Agent 模式下，按 `agent_mode_servers` 返回 MCP 工具
- [ ] Agent 模式下，上传附件以 `<attachment_uploads>` 注入，PDF / Excel 优先暴露 derived Markdown 虚拟路径
- [ ] Agent 模式下，最大迭代次数为 20
- [ ] 非 Agent 模式下，行为与之前一致

---

## 六、执行顺序

1. 前端类型定义和常量修改
2. 前端 UI 组件修改
3. 前端 hooks 和欢迎页修改
4. 后端 Schema 修改
5. 后端核心逻辑修改
6. 后端提示词模板修改
7. 前后端联调验证
