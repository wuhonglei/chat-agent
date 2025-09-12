# AI Doc Frontend

基于 React + TypeScript + Vite 构建的 AI 文档助手前端应用。

## 技术栈

- **框架**: React 18 + TypeScript
- **构建工具**: Vite 5
- **UI 组件库**: Ant Design 5
- **状态管理**: Redux Toolkit
- **路由**: React Router v6
- **样式**: Tailwind CSS 4
- **HTTP 客户端**: Axios
- **Markdown 渲染**: react-markdown + react-syntax-highlighter

## 项目结构

```
frontend/
├── src/
│   ├── components/          # 可复用组件
│   │   ├── Chat/           # 聊天相关组件
│   │   ├── Document/       # 文档管理组件
│   │   └── Layout/         # 布局组件
│   ├── pages/              # 页面组件
│   │   ├── ChatPage.tsx    # 聊天页面
│   │   ├── DocumentsPage.tsx # 文档管理页面
│   │   └── KnowledgeBasePage.tsx # 知识库页面
│   ├── services/           # API 服务
│   ├── store/              # Redux store
│   ├── types/              # TypeScript 类型定义
│   ├── utils/              # 工具函数
│   ├── App.tsx             # 应用根组件
│   ├── main.tsx            # 应用入口
│   └── index.css           # 全局样式
├── public/                 # 静态资源
├── .env.example           # 环境变量示例
├── Dockerfile             # Docker 配置
├── nginx.conf             # Nginx 配置
├── package.json           # 项目依赖
├── tsconfig.json          # TypeScript 配置
├── vite.config.ts         # Vite 配置
└── tailwind.config.js     # Tailwind CSS 配置
```

## 功能特性

- 📝 **文档管理**: 支持上传、查看和管理文档
- 💬 **智能对话**: 与 AI 助手进行自然语言对话
- 🔍 **知识检索**: 基于上传的文档进行智能问答
- 📚 **知识库管理**: 创建和管理多个知识库
- 🎨 **响应式设计**: 适配桌面和移动设备
- 🌐 **实时通信**: 支持 SSE (Server-Sent Events) 流式响应

## 开发环境

### 前置要求

- Node.js >= 18
- npm >= 9 或 yarn >= 1.22

### 环境变量

复制 `.env.example` 为 `.env` 并配置：

```bash
cp .env.example .env
```

配置项：
- `VITE_API_BASE_URL`: 后端 API 地址

### 安装依赖

```bash
npm install
```

### 启动开发服务器

```bash
npm run dev
```

应用将在 http://localhost:5173 启动

### 其他命令

```bash
# 类型检查
npm run type-check

# 代码检查
npm run lint

# 构建生产版本
npm run build

# 预览生产构建
npm run preview
```

## 生产部署

### Docker 部署

```bash
# 构建镜像
docker build -t ai-doc-frontend .

# 运行容器
docker run -d \
  -p 80:80 \
  --name ai-doc-frontend \
  ai-doc-frontend
```

### 手动部署

1. 构建生产版本：
```bash
npm run build
```

2. 将 `dist` 目录部署到 Web 服务器（如 Nginx）

3. 配置 Nginx（参考 `nginx.conf`）：
   - 配置静态文件服务
   - 配置 API 代理
   - 配置 SPA 路由

## API 集成

前端通过 `/api` 路径代理到后端服务，主要接口包括：

- **文档管理**
  - `POST /api/documents/upload` - 上传文档
  - `GET /api/documents` - 获取文档列表
  - `DELETE /api/documents/{id}` - 删除文档

- **对话交互**
  - `POST /api/chat/stream` - 流式对话（SSE）
  - `GET /api/chat/history` - 获取对话历史

- **知识库管理**
  - `GET /api/knowledge-bases` - 获取知识库列表
  - `POST /api/knowledge-bases` - 创建知识库
  - `PUT /api/knowledge-bases/{id}` - 更新知识库

## 开发规范

- 使用 TypeScript 进行类型安全开发
- 遵循 ESLint 代码规范
- 组件使用函数式组件 + Hooks
- 使用 Redux Toolkit 进行状态管理
- 样式使用 Tailwind CSS utility classes
- 代码提交前进行类型检查和 lint 检查

## License

MIT