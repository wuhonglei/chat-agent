---
name: workspace文件树预览接入
overview: 为“网站创建”场景新增 workspace 文件树与文件内容读取 REST 接口，并在 ChatPage 右侧预览面板接入基于 Ant Design X Folder 的项目结构预览。点击文件时实时从后端读取最新内容。
todos:
  - id: backend-workspace-read-api
    content: 新增 workspace 文件树与文件内容只读 REST 接口，并复用现有 workspace 路径安全逻辑
    status: completed
  - id: frontend-project-block
    content: 扩展 PreviewableBlock 与 BlockPreviewPanel，新增 project 分支与 ProjectPreview 挂载
    status: completed
  - id: frontend-workspace-service
    content: 新增 workspace 前端 service，封装文件树与文件内容请求
    status: completed
  - id: chatpage-entry
    content: 在网站创建相关消息/工具结果处增加 openPreview(ProjectBlock) 入口
    status: completed
  - id: integration-verify
    content: 完成端到端联调与边界场景验收（模板复制、文件更新、非法路径）
    status: completed
isProject: false
---

# Workspace 文件树预览实现计划

## 目标与范围
- 在前端“网站创建”场景中，将右侧预览扩展为项目文件结构视图（`Folder` 风格），并支持点击文件后实时读取最新内容。
- 后端新增只读 REST 接口，面向用户 `workspace` 目录（`backend/data/user_data/<user_id>/workspaces/<workspace_id>`）提供：
  - 文件树查询
  - 指定路径文件内容读取
- 前端预览组件落地到 [frontend/src/pages/ChatPage/components/BlockPreviewPanel](frontend/src/pages/ChatPage/components/BlockPreviewPanel)，新增 `ProjectPreview` 子模块。

## 后端改造
- **复用既有 workspace 安全能力**
  - 复用 [backend/app/mcp/mcp_servers/agent_skills_mcp/utils.py](backend/app/mcp/mcp_servers/agent_skills_mcp/utils.py) 的路径解析与目录边界约束能力（例如 `get_workspace_root`、路径校验逻辑），避免重复实现安全规则。
- **新增 workspace 只读 API（REST）**
  - 在 [backend/app/api](backend/app/api) 下新增或扩展 chat 相关路由文件，增加两个接口：
    - `GET /api/workspaces/{workspace_id}/files?depth=...`：返回树结构（目录+文件）。
    - `GET /api/workspaces/{workspace_id}/file-content?path=...`：返回文件文本内容（以及可选 language/mime）。
  - 鉴权与数据隔离：从当前登录态解析 `user_id`，仅允许读取该用户的 workspace。
  - 响应数据建议与 Ant Design X `Folder` 对齐：
    - 树节点字段包含 `title`、`path`、`children`，文件节点可带 `content`（可选，默认不内联）。
- **模板复制场景可感知性**
  - 不额外做“copy 事件”协议改造，采用“查询即真相”策略：
    - 前端进入项目预览或收到会话 `done` 后调用文件树接口，天然覆盖 `write_workspace_file` 与模板复制（包括 `cp -r`）结果。

## 前端改造
- **扩展预览 block 类型**
  - 在 [frontend/src/interfaces/contentBlock.ts](frontend/src/interfaces/contentBlock.ts) 新增 `ProjectBlock`（示例字段：`workspaceId`、`title`、`scene`）。
- **扩展侧栏分发**
  - 修改 [frontend/src/pages/ChatPage/components/BlockPreviewPanel/index.tsx](frontend/src/pages/ChatPage/components/BlockPreviewPanel/index.tsx) 的 `switch`，新增 `project` 分支，挂载 `ProjectPreview`。
- **新增 ProjectPreview 组件**
  - 新建目录：`frontend/src/pages/ChatPage/components/BlockPreviewPanel/ProjectPreview`。
  - 组件职责：
    - 左侧：`Folder` 展示文件树。
    - 右侧：文件内容预览（代码高亮/纯文本）。
    - 点击文件：实时调用后端 `file-content` 接口，不走本地缓存（按你选择的“每次点击实时请求”）。
- **新增前端 service**
  - 在 [frontend/src/services](frontend/src/services) 下新增 `workspace.ts`：
    - `getWorkspaceFileTree(workspaceId, depth)`
    - `getWorkspaceFileContent(workspaceId, path)`
  - 统一复用现有 `apiClient` 规范、错误处理与取消请求策略。
- **接入触发点（网站创建场景）**
  - 在工具结果渲染或消息动作区域增加“打开项目结构预览”入口（复用 `openPreview` 上下文），构造 `ProjectBlock` 打开右侧面板。
  - 首次打开时拉取文件树；之后在会话 `done` 或用户手动刷新时重新拉取，确保包含后端复制模板后的最新结构。

## 接口契约（建议）
- `GET /api/workspaces/{workspace_id}/files`
  - 返回：`{ treeData: FolderTreeData[], workspaceId: string, updatedAt?: string }`
- `GET /api/workspaces/{workspace_id}/file-content?path=src/App.tsx`
  - 返回：`{ path: string, content: string, language?: string, size?: number, updatedAt?: string }`
- 错误码建议：
  - `403`：跨用户访问
  - `404`：workspace 或文件不存在
  - `400`：非法路径（越界/空路径）

## 联调与验收
- **功能验收**
  - 触发“网站创建”后，右侧可打开项目结构，展示模板复制后的目录树。
  - 点击任意文件，右侧展示该文件最新内容；同一文件被后端重写后再次点击能看到新内容。
- **边界验收**
  - 超深目录 `depth` 限制生效；二进制或超大文件给出友好提示。
  - 非法路径和跨用户访问被拒绝。
- **回归点**
  - 不影响现有 `PdfBlock` / `HtmlBlock` / `CodeExecBlock` 预览流程。

## 依赖与注意事项
- 先确认 `@ant-design/x` 当前版本是否可直接导出 `Folder`。若版本/导出不匹配，需先升级并做最小兼容改造。
- 为避免 UI 抖动，文件树加载与文件内容加载分别维护独立 loading/error 状态。

```mermaid
flowchart LR
userAction[User开启网站创建预览] --> openPreview[openPreview(ProjectBlock)]
openPreview --> treeApi[GET文件树]
treeApi --> folderView[Folder渲染目录]
folderView --> clickFile[点击文件节点]
clickFile --> contentApi[GET文件内容(path)]
contentApi --> fileView[右侧内容展示]
chatDone[会话done事件] --> treeApi
```
