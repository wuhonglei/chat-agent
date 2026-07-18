# 智能文档问答系统需求文档（按当前代码结构修订）

> 状态：以当前仓库实现为基准（包含认证、会话管理、MCP 工具与流式问答）。

## 1. 项目概述

### 1.1 背景
项目面向知识问答场景，提供“多源信息获取 + 大模型生成 + 会话管理”的完整链路，支持 Web 前端交互、后端流式响应与会话数据持久化。

### 1.2 目标
- 提供稳定的 AI 问答能力（含流式响应和多轮会话）
- 具备可维护的会话与消息管理能力
- 支持可扩展的 MCP 工具体系（联网搜索、天气、代码执行等）
- 提供可用的用户认证与鉴权机制（短信/微信 + JWT）

### 1.3 范围
当前范围覆盖：
- 认证与授权（短信、微信、JWT）
- 会话与消息管理
- SSE 流式对话接口
- MCP 工具接入与组件工具调用
- 聊天附件上传、预览、RAG 检索与 Agent 模式按需读取
- 前后端分离 Web 应用

不在当前范围内或未完整落地：
- 独立的“知识库管理中心（增删改查、导出下载）”产品化界面
- 独立 `/api/retrieval/*` 检索开放接口

## 2. 功能需求

### 2.1 用户与认证
- 支持短信验证码发送与登录
- 支持微信登录初始化与登录回调
- 登录后通过 JWT 访问受保护接口
- 支持登出并更新用户最后登出时间

### 2.2 对话与消息
- 创建对话、编辑标题、删除对话
- 分页查询对话列表
- 获取指定会话消息历史
- 删除单条消息

### 2.3 AI 问答
- 支持 `POST /api/chat/stream` 流式输出
- 支持 think mode、Agent mode
- 支持组件工具条件触发与结构化数据输出
- 支持会话上下文裁剪与摘要（由后端服务执行）
- 支持图片、PDF、Excel、Markdown、纯文本/代码文件作为用户消息附件
- 普通模式下，文本类附件（含 PDF / Excel 派生 Markdown）通过附件 RAG 注入 `<attachment_context>`
- Agent 模式下，后端注入 `<attachment_uploads>` 文件清单，模型通过 file MCP 按需读取 `/mnt/user-data/uploads/...`

### 2.4 MCP 工具
当前内置并由后端统一管理的 MCP 服务：
- `context7`
- `weather`
- `tavily`
- `code`
- `time`
- `file`
- `shell`
- `skill_manager`
- `zread`（可通过配置接入）

普通对话与 Agent 模式暴露给模型的服务列表分别由 `normal_mode_servers`、`agent_mode_servers` 配置控制。

### 2.5 用户信息与记忆
- 获取与更新用户信息
- 查询/删除用户记忆（Memories）
- 上传头像文件

## 3. 技术架构（当前实现）

### 3.1 前端
- React + TypeScript + Vite+
- Ant Design 6
- Redux Toolkit
- 路由：`/chat`、`/chat/:conversationId`、`/login`、`/markdown`
- API 基础路径：`/api`（前端代理到后端）

### 3.2 后端
- FastAPI + SQLModel + Alembic
- PostgreSQL（pgvector）
- fastmcp
- 配置中心可选（Nacos）
- OpenAI 兼容 LLM 调用

### 3.3 部署
- Docker Compose 三服务：`postgres`、`backend`、`frontend`
- 默认端口：5432 / 8000 / 3000

## 4. 关键接口（当前实现）

### 4.1 认证
- `POST /api/auth/sms/send`
- `POST /api/auth/sms/login`
- `POST /api/auth/logout`
- `POST /api/auth/wechat/init`
- `POST /api/auth/wechat/login`

### 4.2 会话与消息
- `POST /api/conversation/register`
- `GET /api/conversation/list`
- `GET /api/conversation/detail/{conversation_id}`
- `GET /api/conversation/{conversation_id}/messages`
- `PUT /api/conversation/update/{conversation_id}`
- `DELETE /api/conversation/delete/{conversation_id}`
- `DELETE /api/message/delete/{message_id}`

### 4.3 聊天与健康检查
- `POST /api/chat/stream`
- `GET /api/health`
- `GET /api/health/mcp`
- `GET /api/health/mcp_config`

### 4.4 用户与文件
- `GET /api/user/detail`
- `PUT /api/user/update_info`
- `GET /api/user/memories`
- `DELETE /api/user/memories/{memory_id}`
- `POST /api/avatars/upload`
- `GET /api/avatars/{filename}`
- `POST /api/file/upload`
- `GET /api/file/preview/{user_id}/{storage_key}`

## 5. 非功能性要求

- 日志可追踪：请求链路具备 request id
- 数据可靠：会话与消息持久化
- 可扩展：MCP 服务可扩展接入
- 可部署：支持本地开发与 Docker Compose 部署

## 6. 风险与约束

- 外部依赖（LLM、第三方 MCP、配置中心）可用性会影响体验
- 认证、短信、微信等外部服务需要正确配置密钥
- 数据库迁移与初始化流程需按后端文档执行

## 7. 文档关系

- 部署与运行：`README.md`、`backend/README.md`、`frontend/README.md`
- 会话管理细化：`docs/会话管理.md`
- 认证细化：`docs/认证流程.md`
- 其他专题：见 `docs/README.md`
