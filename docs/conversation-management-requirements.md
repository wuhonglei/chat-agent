# AI 聊天助手对话管理需求文档（按当前实现修订）

> 状态：现网实现 + 规划项混合文档。接口路径以当前 `backend/app/api/conversation.py` 与 `chat.py` 为准。

## 1. 项目概述

### 1.1 项目背景
基于现有的AI聊天助手系统，增加完整的对话管理功能，使用能够方便地管理多个聊天会话，提升用户体验和使用效率。

### 1.2 目标用户
- 需要与AI助手进行多场景对话的用户
- 需要管理多个对话主题的专业用户
- 需要保存和回顾历史对话记录的用户

## 2. 功能需求

### 2.1 对话创建功能
**功能描述**: 用户通过后端 `POST /api/conversation/register` 接口创建新的对话会话，后端按照统一响应格式返回新建会话详情。

**用户故事**:
- 作为用户，我希望能够快速开始一个新的对话
- 作为用户，我希望新对话有默认的标题，并且可以编辑

**验收标准**:
- [ ] 点击"新建对话"按钮会调用 `POST /api/conversation/register`
- [ ] 前端在未填写标题时向接口提交默认标题（例如 `新对话`），后端会将 `created_by` 标记为 `default`
- [ ] 接口返回的 `ApiResponse` 中 `code=0` 且 `data` 包含 `id`、`title`、`created_at`、`updated_at`、`message_count`
- [ ] 创建完成后自动切换到该对话并准备接受消息

### 2.2 对话删除功能
**功能描述**: 用户可以通过 `DELETE /api/conversation/delete/{conversation_id}` 删除不需要的对话会话，接口会返回被删除的会话 ID。

**用户故事**:
- 作为用户，我希望能够删除不需要的对话
- 作为用户，我希望删除对话时有确认提示，防止误删

**验收标准**:
- [ ] 在对话列表中点击删除按钮前先弹出二次确认
- [ ] 删除动作会调用 `DELETE /api/conversation/delete/{conversation_id}`
- [ ] 接口返回 `ApiResponse` 且 `code=0`，`data` 为已删除的会话 ID
- [ ] 删除当前正在进行的对话时，前端自动切换到最新的其它会话或创建新会话

### 2.3 对话标题编辑功能
**功能描述**: 用户可以通过 `PUT /api/conversation/update/{conversation_id}` 编辑对话的标题，后端会持久化更新并返回最新的会话信息。

**用户故事**:
- 作为用户，我希望对话标题能够自动基于对话内容生成，一旦生成后，后续对话不会再次自动生成
- 作为用户，我希望能够编辑对话标题来标识不同主题

**验收标准**:
- [ ] 点击对话标题可以进入编辑模式
- [ ] 输入框支持手动输入自定义标题，长度限制 50 个字符
- [ ] 保存时调用 `PUT /api/conversation/update/{conversation_id}`，请求体包含 `id` 与新标题
- [ ] 接口返回 `ApiResponse` 且 `code=0`，`data` 为更新后的会话信息
- [ ] 标题自动生成功能通过聊天流式接口的 `title` 事件触发（见 5.4 节）

### 2.4 对话历史保存功能
**功能描述**: 所有对话内容和历史记录通过消息接口保存在服务端，可通过 `GET /api/conversation/{conversation_id}/messages` 获取。

**用户故事**:
- 作为用户，我希望我的对话历史能够被安全保存
- 作为用户，我希望能够随时访问之前的对话内容

**验收标准**:
- [ ] 对话消息由聊天服务实时写入数据库，刷新页面后历史保持不变
- [ ] 切换对话时调用 `GET /api/conversation/{conversation_id}/messages` 获取指定会话消息列表
- [ ] 接口返回的消息列表与数据库时间顺序一致，包含推理内容、工具调用等元信息
- [ ] 支持至少 1000 条消息的分页或懒加载方案

### 2.5 对话列表管理功能
**功能描述**: 提供直观的对话列表界面，通过 `GET /api/conversation/list` 获取会话集合。

**用户故事**:
- 作为用户，我希望能够看到所有对话的列表
- 作为用户，我希望能够快速切换到任意对话

**验收标准**:
- [ ] 显示所有对话的标题、最后更新时间、消息数量
- [ ] 会话列表请求 `GET /api/conversation/list`，接口返回 `ApiResponse`，`data` 中包含 `total`、`offset`、`limit` 以及 `conversations`
- [ ] 按更新时间倒序展示，当前对话高亮
- [ ] 点击会话项后加载对应历史并切换上下文

### 2.6 对话搜索功能（扩展功能）
**功能描述**: 用户可以搜索和筛选对话

**用户故事**:
- 作为用户，我希望能够通过关键词搜索历史对话
- 作为用户，我希望能够按日期筛选对话

**验收标准**:
- [ ] 支持按对话标题搜索
- [ ] 支持按对话内容搜索
- [ ] 支持按日期范围筛选
- [ ] 搜索结果高亮显示匹配的关键词

## 3. 技术需求

### 3.1 前端技术要求
- **框架**: 基于React + TypeScript实现
- **状态管理**: 使用Redux Toolkit管理对话状态
- **UI组件**: 使用Ant Design组件库
- **样式**: 使用Tailwind CSS

### 3.2 后端技术要求
- **框架**: 基于 FastAPI 实现
- **数据存储**: 使用 SQLModel + PostgreSQL 持久化会话与消息
- **API 设计**: RESTful API + SSE 流式接口组合
- **数据格式**: JSON 数据交换，统一使用 `ApiResponse` 包裹

### 3.3 数据模型设计

#### 用户模型 (User)
```python
class User:
    id: str                    # 用户唯一标识
    name: str                 # 用户名
    email: str                # 用户邮箱
    avatar: str                # 用户头像
    phone: str                 # 用户手机号
    role: str                  # 用户角色
    status: str                # 用户状态
    created_at: datetime       # 创建时间
    updated_at: datetime       # 更新时间
```

#### 对话模型 (Conversation)
```python
class Conversation:
    id: str                    # 对话唯一标识
    title: str                 # 对话标题
    created_by: str            # 标题创建方式: default/user/llm
    user_id: str              # 用户ID（预留扩展）
    created_at: datetime       # 创建时间
    updated_at: datetime       # 更新时间
    message_count: int         # 消息数量
    is_active: bool           # 是否为活跃对话
```

#### 消息模型 (Message)
```python
from typing import Any

class Message:
    id: str                              # 消息唯一标识
    conversation_id: str                 # 所属对话ID
    role: str                            # 消息角色: "user" | "assistant"
    content: str                         # 消息内容
    timestamp: datetime                  # 时间戳（数据库字段名为 created_at）
    reasoning: str | None                # 推理内容（仅助手消息使用，用户消息为 None）
    tool_calls: list[AssistantToolCallMessage] | None    # 工具调用列表（仅助手消息使用，用户消息为 None）
    metadata: dict[str, Any]              # 元数据（模型调用、配置）
```

**数据库设计说明**：
- **统一表存储**：用户消息和助手消息存储在同一个 `messages` 表中，通过 `role` 字段区分类型
- **不建议分表**：虽然两种消息类型有字段差异，但：
  1. 查询模式主要按 `conversation_id` 获取完整对话序列，需要保持时间顺序
  2. 用户和助手消息是成对出现的，业务逻辑强关联
  3. 统一表查询简单高效：`WHERE conversation_id = ? ORDER BY timestamp`
  4. 分表需要 JOIN/UNION 操作，增加复杂度和性能开销
- **索引建议**：
  - 主键：`id`
  - 复合索引：`(conversation_id, timestamp)` 用于按对话查询消息序列
  - 索引：`role` 仅在需要单独统计或筛选某种类型消息时使用

## 4. 用户界面设计

### 4.1 布局结构
```
┌─────────────────────────────────────────────────────────┐
│                      Header                             │
├─────────────┬───────────────────────────────────────────┤
│             │                                           │
│  Sidebar    │            Chat Area                     │
│             │                                           │
│  + 新建对话  │  ┌─────────────────────────────────────┐  │
│             │  │           Conversation Title         │  │
│  对话列表    │  ├─────────────────────────────────────┤  │
│  ● 对话1     │  │                                     │  │
│  ● 对话2     │  │         Messages List               │  │
│  ● 对话3     │  │                                     │  │
│     ...      │  │                                     │  │
│             │  └─────────────────────────────────────┘  │
│             │                                           │
│             │  ┌─────────────────────────────────────┐  │
│             │  │           Input Area                │  │
│             │  └─────────────────────────────────────┘  │
└─────────────┴───────────────────────────────────────────┘
```

### 4.2 交互设计
- **新建对话**: 侧边栏顶部显眼的"+"按钮
- **切换对话**: 点击左侧对话列表中的任意对话
- **编辑标题**: 点击当前对话标题，支持内联编辑
- **删除对话**: 悬停对话项时显示删除按钮

### 4.3 响应式设计
- **桌面端**: 固定侧边栏布局
- **平板端**: 可折叠侧边栏
- **移动端**: 抽屉式侧边栏

## 5. API接口设计

### 5.1 统一响应格式
所有 REST 接口遵循 `ApiResponse` 结构：
```
{
  "code": 0,
  "msg": "操作成功",
  "data": {...}
}
```
- `code=0` 表示成功，非 0 表示失败
- `msg` 返回友好提示
- `data` 携带实际业务数据

### 5.2 对话管理接口（/api/conversation）

#### 创建对话
```
POST /api/conversation/register
Request Body:
{
  "title": "可选的自定义标题"   // 未填写时前端传入默认标题
}

Success Response:
{
  "code": 0,
  "msg": "对话创建成功",
  "data": {
    "id": "conv_456",
    "title": "新对话",
    "created_by": "default",
    "created_at": "2024-01-01T16:00:00Z",
    "updated_at": "2024-01-01T16:00:00Z",
    "message_count": 0
  }
}
```

#### 获取对话列表
```
GET /api/conversation/list

Success Response:
{
  "code": 0,
  "msg": "获取对话列表成功",
  "data": {
    "total": 2,
    "offset": 0,
    "limit": 2,
    "conversations": [
      {
        "id": "conv_123",
        "title": "关于Python的讨论",
        "created_by": "llm",
        "created_at": "2024-01-01T10:00:00Z",
        "updated_at": "2024-01-01T15:30:00Z",
        "message_count": 15
      }
    ]
  }
}
```

#### 获取对话详情
```
GET /api/conversation/detail/{conversation_id}
```
成功返回 `ConversationInfo`，结构与列表项一致。

#### 更新对话标题
```
PUT /api/conversation/update/{conversation_id}
Request Body:
{
  "id": "conv_123",
  "title": "新的对话标题"
}
```
成功后返回更新后的 `ConversationInfo`。

#### 删除对话
```
DELETE /api/conversation/delete/{conversation_id}
```
成功后 `data` 返回被删除的 `conversation_id`。

### 5.3 消息管理接口（/api/conversation/{conversation_id}/messages）

#### 获取对话历史
```
GET /api/conversation/{conversation_id}/messages

Success Response:
{
  "code": 0,
  "msg": "获取消息列表成功",
  "data": {
    "total": 2,
    "offset": 0,
    "limit": 2,
    "messages": [
      {
        "id": "msg_123",
        "conversation_id": "conv_123",
        "role": "user",
        "content": "用户消息内容",
        "reasoning": null,
        "tool_calls": null,
        "message_metadata": {},
        "created_at": "2024-01-01T10:00:00Z"
      },
      {
        "id": "msg_124",
        "conversation_id": "conv_123",
        "role": "assistant",
        "content": "助手回复内容",
        "reasoning": "思维链片段",
        "tool_calls": [
          {
            "id": "call_abc123",
            "type": "function",
            "function": {
              "name": "search_web",
              "arguments": "{\"query\": \"Python教程\"}"
            }
          }
        ],
        "message_metadata": {},
        "created_at": "2024-01-01T10:00:05Z"
      }
    ]
  }
}
```

### 5.4 聊天流式接口（/api/chat）

#### 获取助手回复（流式）
```
POST /api/chat/stream
Content-Type: application/json

Request Body:
{
  "message": "这段代码的作用是什么？",
  "conversation_id": "conv_123",
  "history": [
    {"role": "user", "content": "你好"},
    {"role": "assistant", "content": "你好，很高兴为你服务"}
  ],
  "regenerate_title": false,
  "think_mode": false
}
```
- 返回 `text/event-stream`，事件类型包括：
  - `reasoning`：模型推理分段
  - `content`：助手回复正文
  - `tool_call`：工具调用进度（start/done/error）
  - `title`：当 `regenerate_title=true` 或满足自动触发条件时返回新标题（含 `id`、`title`）
  - `done`：结束标记
- 客户端需要解析 SSE 数据并刷新消息与标题

## 5.5 已确认不在当前实现范围

- `POST /api/chat`（非流式）接口：当前未提供，统一使用 `POST /api/chat/stream`
- 独立 `/api/retrieval/*` 检索接口：当前未在主应用注册
- `/conversations` 风格路径：当前实现统一为 `/api/conversation/*`

## 6. 实现计划

### 阶段一：基础对话管理（核心功能）
1. **后端开发**
   - 实现对话数据模型
   - 创建对话管理API
   - 集成现有的聊天功能

2. **前端开发**
   - 创建对话列表组件
   - 实现对话切换功能
   - 集成现有的聊天界面

### 阶段二：用户体验优化
1. **界面优化**
   - 完善交互细节
   - 添加加载状态和错误处理
   - 实现响应式设计

2. **功能增强**
   - 自动标题生成
   - 对话搜索功能
   - 批量操作功能

### 阶段三：高级功能（可选）
1. **数据导出**
   - 支持导出对话历史
   - 支持多种格式（Markdown、JSON）

2. **智能分类**
   - 基于内容自动分类对话
   - 标签系统

## 7. 非功能性需求

### 7.1 性能要求
- 对话列表加载时间 < 500ms
- 对话切换响应时间 < 200ms
- 支持至少1000个对话的管理

### 7.2 安全要求
- 对话数据加密存储
- 用户隔离（多用户支持预留）
- 防止SQL注入和XSS攻击

### 7.3 可用性要求
- 系统可用性 > 99.5%
- 数据备份和恢复机制
- 错误日志记录

## 8. 风险分析

### 8.1 技术风险
- **数据一致性**: 确保对话状态在前后端保持同步
- **性能问题**: 大量对话时的性能优化
- **存储容量**: 历史数据的存储容量管理

### 8.2 缓解措施
- 实现增量同步机制
- 使用分页和懒加载
- 实现数据清理和归档策略


**文档版本**: v1.2
**创建日期**: 2024-10-31
**最后更新**: 2025-11-08
**创建人**: AI Assistant
