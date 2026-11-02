# Chat Agent Frontend

基于 React 19 + TypeScript + Vite+ 的前端应用，负责会话交互、登录流程、流式消息渲染和组件工具展示。

## 技术栈（当前实现）

- React 19
- TypeScript
- Vite+（`vp`）
- Ant Design 6（含 `@ant-design/x`、`@ant-design/x-markdown`）
- React Router 7
- Redux Toolkit + 中间件
- Tailwind CSS 4
- Axios + `fetch-event-source`（SSE）

## 目录结构（核心）

```text
frontend/
├── src/
│   ├── pages/                 # ChatPage / WelcomePage / MemoriesPage / LoginPage / MarkdownPage
│   ├── routes/                # 路由配置
│   ├── services/              # API 调用层
│   ├── store/                 # Redux store 与中间件
│   ├── interfaces/            # TS 接口定义
│   ├── componentTools/        # 组件工具与 schema
│   ├── indexDB/               # 本地存储（Dexie）
│   ├── hooks/                 # 业务 hooks
│   ├── components/            # 通用组件与布局
│   ├── styles/index.css       # 全局样式入口
│   ├── App.tsx
│   └── main.tsx
├── public/component-schemas/  # 对外提供组件 schema
├── vite-plugins/              # 构建时 schema 生成插件
├── vite.config.ts
├── nginx.conf
└── Dockerfile
```

## 路由

- `/`：重定向到 `/chat`
- `/chat`：新会话欢迎页
- `/chat/:conversationId`：会话详情页
- `/memories`：用户记忆管理（分页 / 搜索 / 治理状态 / 类型 / **类别** / 创建日期筛选）
- `/login`：登录页
- `/login/wechat/callback`：微信登录回调
- `/markdown`：Markdown 展示页

## API 对接

前端通过 `apiClient` 统一访问 `/api` 前缀接口（`src/services/base.ts`）：

- 聊天：`POST /api/chat/stream`、`POST /api/chat/stream/resume`、`GET /api/chat/models`
- 会话：`/api/conversation/*`
- 用户：`/api/user/*`
- 认证：`/api/auth/*`
- 健康检查：`/api/health*`
- 头像：`POST /api/avatars/upload`；文件：`POST /api/file/upload`
- 静态站：`GET /api/sites/me`、`POST /api/sites/`、`POST /api/sites/{slug}/republish`、`DELETE /api/sites/{slug}`（`src/services/sites.ts`）

## Chat 内容块与附件（当前实现）

### 用户消息 `contentBlocks`

前端发送消息时，按 `UserContentBlock[]` 组织请求体（见 `src/interfaces/contentBlock.ts`）：

- `text`：文本块
- `image`：图片附件块
- `pdf`：PDF 附件块
- `excel`：Excel 附件块（`.xlsx`）
- `docx`：Word 附件块（`.docx`）
- `pptx`：PowerPoint 附件块（`.pptx`）
- `markdown`：Markdown 附件块
- `text_file`：纯文本 / 代码附件块

发送时会先写入文本块，再按上传顺序追加附件块（`buildUserContentBlocks`）。

### 附件上传约束

`ChatInput` 当前约束（`src/pages/ChatPage/components/ChatInput/util.ts`）：

- 支持类型：图片（JPEG/PNG/GIF/WebP）、PDF、Excel（`.xlsx`）、Word（`.docx`）、PowerPoint（`.pptx`）、Markdown（`.md` / `.markdown` / `text/markdown`）和纯文本 / 代码文件
- 纯文本 / 代码扩展名由 `TEXT_FILE_ACCEPT` 维护，覆盖 `.csv`、`.tsv`、`.txt`、`.log`、`.py`、`.js`、`.ts`、`.tsx`、`.vue`、`.sql`、`.go` 等常见格式
- 单文件大小：不超过 `10MB`
- 单次消息附件数量：最多 `5` 个
- 上传接口：`POST /api/file/upload`（`src/services/file.ts`）
- 上传超时：`300000ms`（5 分钟，覆盖 MinerU 轮询）
- 当前模型不支持图片时，两条入口不一致：
  - 点击附件按钮走 `openAttachmentPicker`，`accept` 换成 `CHAT_ATTACHMENT_ACCEPT_PDF_ONLY`（PDF、`.xlsx`、`.docx`、`.pptx`）。常量名虽带 PDF_ONLY，但不含 Markdown / 纯文本，也不只剩 PDF
  - 粘贴与拖到页面仍用完整 `CHAT_ATTACHMENT_ACCEPT`，再由 `beforeUpload` / `onPasteFile` 拒绝图片并提示切换模型；Markdown 与文本/代码文件可以继续传

### 附件预览行为

- 图片：在用户消息中以 `FileCard` 图片卡片展示。图片卡固定 `256×256`，`object-fit: contain`；加载失败用内置 404 图。图片不进侧栏预览
- PDF / Excel / Word / PowerPoint / Markdown / 纯文本：聊天页点击后打开右侧 `BlockPreviewPanel`。只有没传入 `onPreviewBlock` 时才 `window.open` 新标签。小屏（body 宽度 ≤ 768px）侧栏默认占满视口（至少 280px），不会改成直接下载
- PDF：`react-pdf` 渲染；若块上有 `markdown.url`，可在 PDF / Markdown 间切换
- Excel：默认 SheetJS 多 sheet 表格；有派生 Markdown 时可切到 Markdown
- Word：动态加载 `docx-preview` 的 `renderAsync`（分页、忽略版心宽度）；有派生 Markdown 时可在文档 / Markdown 间切换
- PowerPoint：动态加载 `pptx-preview`，`mode: "slide"`，宽度跟侧栏、高度为宽度的 9/16；有派生 Markdown 时可切换
- Markdown：作为独立 `MarkdownBlock` 打开右侧预览。PDF / Excel / Word / PowerPoint 转写出的 Markdown 复用同一套 Markdown 视图，不是单独的块类型
- 纯文本 / 代码文件：`.csv` / `.tsv` 以表格预览，其它文本/代码通过 `CodeHighlighter` 按扩展名高亮
- HTML：代码块头部「预览」用侧栏 iframe `srcDoc`（当前未设 `sandbox`）。工作区 HTML：已发布则 iframe 走站点公网 URL；未发布且行数 ≥ 50 默认预览，否则源码
- 工作区项目：`ProjectPreview` 浏览 agent 工作区。存在 `outputs/app-dist` 或 `outputs/index.html` 时提供「文件 / 运行」与发布 / 复制链接 / 下线；自定义 slug 走 REST，占用展示 409，不静默改名。`workspaceId` 即 `conversation_id`
- 工作区文件（与上面的聊天附件预览分开）：`.xlsx`/`.xls` 表格，`.png`/`.jpg`/`.jpeg`/`.gif`/`.webp`/`.ico` 图片，`.svg` 与 `.mmd`/`.mermaid` 可在预览和源码间切换。工作区里的 `.pdf` / `.docx` / `.pptx` 属于二进制占位，不会套用聊天附件的 PDF / Word / PPT 预览。侧栏可全屏，不新开路由。细节见 `frontend/docs/conversation.md` 第 8 节

`PreviewableBlock` 当前覆盖 `pdf | excel | docx | pptx | markdown | text_file | html | code_exec | project`，入口为 `src/pages/ChatPage/components/BlockPreviewPanel/index.tsx`。

### 文件工具结果展示

`file` MCP 的 `edit_file` 工具参数会在消息中渲染行级 diff（`FileDiffView`）：

- 使用 LCS 计算逐行新增 / 删除 / 上下文
- 当 `(oldLines + 1) * (newLines + 1) > 4_000_000` 时退化为“整段删除 + 整段新增”，避免浏览器内存压力
- `replaceAll` 参数会在 diff 头部显示为标签

相关实现：

- `src/pages/ChatPage/components/ChatMessage/UserMessage/components/UserMessageDisplayContent.tsx`
- `src/pages/ChatPage/components/BlockPreviewPanel/*`
- `src/pages/ChatPage/components/MarkdownContainer/components/HtmlPreviewHeader.tsx`
- `src/pages/ChatPage/components/ChatMessage/AssistantMessage/ContentBlocksRender/ToolBlockRender/registry/components/FileDiffView.tsx`

## SSE 事件约定（`/api/chat/stream`）

流式响应通过 `fetch-event-source` 处理，事件数据统一解析为：

- `ack`
- `refresh_conversation`
- `title`
- `content_block`
- `done`
- `error`

其中 `content_block` 支持的增量操作包括：

- `append`
- `delta`
- `tool_delta`
- `finalize_round`
- `done`

服务端会在 SSE JSON envelope 中注入 `seq`。前端在流式处理中记录最近消费的 `seq`，页面恢复时可调用 `POST /api/chat/stream/resume` 继续读取仍处于活动状态的助手消息流。

前端事件类型定义见 `src/interfaces/apiRequest.ts`，流式处理入口见 `src/services/chat.ts` 与 `src/hooks/chat.ts`。

## 模型选择与图片输入

模型下拉列表由 `GET /api/chat/models` 返回，字段包括：

- `modelId`：聊天请求中的模型 ID，格式为 `provider/model_name`（如 `dashscope/kimi-k2.6`）
- `title` / `description`：下拉展示文案
- `imageSupport`：是否允许图片输入

当当前消息含图片上下文时，`ModelSelect` 会禁用 `imageSupport=false` 的模型；发送时后端也会再次校验。

## 开发指南

### 前置要求

- Node.js（建议与 Vite+ 兼容版本）
- 已安装 Vite+ CLI

### 环境准备

```bash
cd frontend
source ~/.vite-plus/env
cp .env.example .env
vp install
```

`.env.example` 关键配置：

- `VITE_PROXY_TARGET`：开发代理目标（默认代理后端）

### 启动开发服务器

```bash
vp dev
```

默认地址：`http://localhost:3000`

### 常用命令

```bash
vp lint .
vp fmt ./src
vp check
vp build
vp preview
```

## 构建与部署

### Docker

```bash
docker build -t chat-agent-frontend .
docker run -d -p 3000:3000 --name chat-agent-frontend chat-agent-frontend
```

### 手动部署

1. `vp build`
2. 部署 `dist/` 到静态服务器
3. 参考 `nginx.conf` 配置 SPA 路由与 `/api` 反向代理

## 说明

- 不要直接使用 `npm`/`pnpm` 命令管理依赖或启动开发服务，统一使用 `vp`。
- `@tailwindcss/vite` 等插件的 `vite` 必须 alias 到 `vite-plus-core`（见 `package.json` overrides）；版本漂移会导致构建失败。
- 若需了解前端专题文档，请查看 `frontend/docs/` 和根索引 `docs/README.md`。
