# AI Doc Frontend

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

- 聊天：`POST /api/chat/stream`
- 会话：`/api/conversation/*`
- 用户：`/api/user/*`
- 认证：`/api/auth/*`
- 健康检查：`/api/health*`
- 文件：`POST /api/file/upload_avatar`

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
docker build -t ai-doc-frontend .
docker run -d -p 3000:3000 --name ai-doc-frontend ai-doc-frontend
```

### 手动部署

1. `vp build`
2. 部署 `dist/` 到静态服务器
3. 参考 `nginx.conf` 配置 SPA 路由与 `/api` 反向代理

## 说明

- 不要直接使用 `npm`/`pnpm` 命令管理依赖或启动开发服务，统一使用 `vp`。
- 若需了解前端专题文档，请查看 `frontend/docs/` 和根索引 `docs/README.md`。
