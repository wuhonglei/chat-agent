# messages 表字段精简计划（已落地状态）

> 更新日期：2026-04-04  
> 适用范围：`backend/app/models/message_db.py` 与 `backend/alembic/versions/*` 当前实现

## 1. 目的

记录 `messages` 表字段精简的**现状**与**运维核验方式**，避免继续按历史“待删除”口径执行重复变更。

## 2. 已完成的字段下线

以下字段已通过 Alembic 迁移删除：

- `component_tool_calls`
- `component_tool_calls_duration`
- `tool_calls_duration`
- `reasoning_duration`
- `content_duration`
- `total_duration`
- `token_stats`
- `embedding_vector`
- `embedding_model`

对应迁移文件：

- `backend/alembic/versions/l8m9n0o1p2q3_remove_component_tool_calls_from_messages.py`
- `backend/alembic/versions/m9n0o1p2q3r4_remove_message_duration_columns.py`
- `backend/alembic/versions/n0o1p2q3r4s5_remove_token_stats_from_messages.py`
- `backend/alembic/versions/o1p2q3r4s5t6_remove_message_embedding_columns.py`

## 3. 当前 `messages` 表核心字段（代码口径）

以 `backend/app/models/message_db.py` 为准，当前核心字段为：

- `id`
- `conversation_id`
- `role`
- `content`
- `created_at`
- `updated_at`
- `reasoning`
- `tool_calls`
- `message_metadata`
- `status`
- `reply_to`

说明：

- `message_metadata` 与 `reply_to` 仍在模型中保留，属于现网字段，不应按“已废弃”处理。

## 4. 部署与排障核验清单

### 4.1 发布前核验

1. 确认目标环境已执行到最新 Alembic 版本（`alembic current`）。
2. 确认应用代码与数据库版本同步（避免“代码已删字段，库未迁移”）。

### 4.2 发布后核验

重点观察：

- 聊天链路成功率（`POST /api/chat/stream`）
- `messages` 写入失败率
- 是否出现列不存在错误（如 `column ... does not exist`）

### 4.3 数据库结构抽样检查（PostgreSQL）

```sql
SELECT column_name
FROM information_schema.columns
WHERE table_name = 'messages'
ORDER BY ordinal_position;
```

如果结果中仍出现已下线字段，请先补齐迁移再排查业务问题。

## 5. 约束与后续维护

- 本文档仅记录已生效状态，不再作为“下一步删字段方案”。
- 若后续继续精简字段，需新增独立变更记录，并同步更新本页“已完成字段下线”章节。
