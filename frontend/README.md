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
│   ├── pages/                 # ChatPage / WelcomePage / LoginPage / MarkdownPage
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

## Chat 内容块与附件（当前实现）

### 用户消息 `contentBlocks`

前端发送消息时，按 `UserContentBlock[]` 组织请求体（见 `src/interfaces/contentBlock.ts`）：

- `text`：文本块
- `image`：图片附件块
- `pdf`：PDF 附件块
- `markdown`：Markdown 附件块

发送时会先写入文本块，再按上传顺序追加附件块（`buildUserContentBlocks`）。

### 附件上传约束

`ChatInput` 当前约束（`src/pages/ChatPage/components/ChatInput/util.ts`）：

- 支持类型：图片（JPEG/PNG/GIF/WebP）、PDF 和 Markdown（`.md` / `.markdown` / `text/markdown`）
- 单文件大小：不超过 `10MB`
- 单次消息附件数量：最多 `5` 个
- 上传接口：`POST /api/file/upload`（`src/services/file.ts`）
- 上传超时：`180000ms`（3 分钟）

### 附件预览行为

- 图片：在用户消息中以 `FileCard` 图片卡片展示
- PDF：
  - 小屏设备点击后直接下载
  - 非小屏优先在右侧 `BlockPreviewPanel` 打开 PDF 预览
- Markdown：作为独立 `MarkdownBlock` 打开右侧预览；PDF 转写出的 Markdown 也复用同一块结构
- HTML：在代码块头部点击“预览”后，使用侧栏 iframe 的 `srcDoc` 预览；当前 iframe 未设置 `sandbox`

相关实现：

- `src/pages/ChatPage/components/ChatMessage/UserMessage/components/UserMessageDisplayContent.tsx`
- `src/pages/ChatPage/components/BlockPreviewPanel/*`
- `src/pages/ChatPage/components/MarkdownContainer/components/HtmlPreviewHeader.tsx`

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
- 若需了解前端专题文档，请查看 `frontend/docs/` 和根索引 `docs/README.md`。
