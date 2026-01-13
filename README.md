# AI Assistant Platform - 智能助手平台

基于 RAG (Retrieval Augmented Generation) 技术的企业级智能助手平台，集成多源搜索、智能问答、文档分析等功能，支持本地文档、云端协作文档和网络资源的智能检索与深度分析。

## 🌟 主要特性

- 🔍 **多源搜索**: 联网搜索、Confluence 内网搜索
- 🤖 **智能问答**: 基于 DeepSeek 大模型的精准回答与深度推理
- 🔗 **外部集成**: 支持 Confluence 等平台
- 💬 **交互体验**: 多轮对话、实时中断、智能滚动、输入折叠
- 📊 **可视化支持**: Mermaid 流程图、思维导图渲染
- 🎨 **优秀交互**: 打字机效果、引用高亮

## 🚀 快速开始

### 环境要求

- Python 3.10+
- Docker & Docker Compose
- DeepSeek API Key

### 安装步骤

1. **克隆项目**
```bash
git clone https://github.com/your-org/ai-doc.git
cd ai-doc
```

2. **配置环境变量**
```bash
cp docker-compose.env.example .env
```

3. **使用 Docker Compose 启动**
```bash
docker-compose up -d
```

配置未变：docker-compose up -d 不会重启正在运行的容器
配置已变：docker-compose up -d 会重新创建容器（会重启）
需要强制重启：使用 docker-compose restart 或 docker-compose up -d --force-recreate

1. **访问应用**
- 前端界面: http://localhost:3000
- 后端 API: http://localhost:8000
- API 文档: http://localhost:8000/docs

### 本地开发

#### 后端开发

```bash
cd backend

# 使用 uv 安装依赖
uv pip install -e .

# 启动开发服务器
uvicorn app.main:app --reload --port 8000
```

#### 前端开发

```bash
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

## 📁 项目结构

```
ai-doc/
├── backend/                 # 后端服务
│   ├── app/
│   │   ├── api/            # API 路由
│   │   ├── core/           # 核心功能
│   │   ├── models/         # 数据模型
│   │   └── services/       # 业务服务
│   ├── pyproject.toml      # 项目配置
│   └── Dockerfile
├── frontend/               # 前端应用
│   ├── src/
│   │   ├── components/     # React 组件
│   │   ├── pages/         # 页面组件
│   │   ├── services/      # API 服务
│   │   └── utils/         # 工具函数
│   └── Dockerfile
├── docker-compose.yml      # Docker 编排
├── requirements.md         # 需求文档
└── README.md              # 项目说明

```

## 🔧 技术栈

### 后端
- **Web 框架**: FastAPI
- **向量数据库**: Chroma
- **LLM**: DeepSeek Chat API
- **缓存**: Redis

### 前端
- **框架**: React
- **UI 组件**: Ant Design
- **状态管理**: Redux
- **构建工具**: Vite

## 📚 API 文档

启动后端服务后，访问 http://localhost:8000/docs 查看完整的 API 文档。

### 主要接口

- `POST /api/chat` - 发送问答请求
- `POST /api/chat/stream` - 流式问答
- `GET /api/knowledge-base/export` - 导出知识库
- `GET /api/knowledge-base/stats` - 知识库统计

## 🔍 使用指南

### 智能问答

1. 在对话框输入您的问题
2. 系统会通过多源搜索获取相关信息
3. 基于搜索结果生成准确回答
4. 点击引用可查看原文内容

### 知识库管理

- 导出整个知识库
- 查看知识库统计信息

## 🛠️ 配置说明

### DeepSeek 配置

```env
DEEPSEEK_API_KEY=your_api_key
DEEPSEEK_MODEL=deepseek-chat
```

### Confluence 集成（可选）

```env
CONFLUENCE_URL=https://your-domain.atlassian.net
CONFLUENCE_USERNAME=your_email@company.com
CONFLUENCE_API_TOKEN=your_token
```



## 🤝 贡献指南

欢迎提交 Issue 和 Pull Request！

## 📄 许可证

MIT License

## 🙏 致谢

- DeepSeek - 提供强大的语言模型
- Chroma - 高效的向量数据库
- LangChain - 优秀的 LLM 应用框架
