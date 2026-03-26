# messages 表字段精简计划

## 背景

基于当前后端代码静态审计与前端类型契约排查，`messages` 表存在一批可能冗余或仅透传字段。为降低线上风险，采用“两阶段”方式推进：先删除高置信冗余字段，再进行观测后分批下线其余候选字段。

---

## 审计结论

### 一、建议优先下线（高置信冗余）

- `embedding_vector`
- `embedding_model`

结论依据：

- 后端仅在 `MessageDb` 模型定义，未发现实际写入、查询、过滤、排序、检索逻辑依赖。
- 聊天主链路与前端展示不依赖上述字段。

### 二、暂不建议直接删除（当前存在消费或潜在契约依赖）

- `reply_to`
- `message_metadata`
- `tool_calls_duration`
- `component_tool_calls_duration`
- `reasoning_duration`
- `content_duration`
- `total_duration`
- `token_stats`

说明：

- `reply_to` 虽未见后端强依赖查询，但作为问答配对语义字段，存在潜在追踪价值。
- `message_metadata` 与统计字段在当前链路中有写入与透传，前端类型存在对应字段映射，需先断契约再删库。

---

## 两阶段执行方案

## 阶段 1（低风险，建议优先执行）

目标：仅删除高置信冗余字段。

删除字段：

- `messages.embedding_vector`
- `messages.embedding_model`

上线步骤：

1. 发布前做数据快照与空值率检查。
2. 执行 Alembic 迁移（drop 两列）。
3. 发布后观察至少一个发布窗口：
   - 聊天接口成功率
   - 消息写入失败率
   - SQL 列不存在异常（unknown column）

回滚策略：

- 回滚 Alembic，恢复两列定义（`embedding_vector` 维度与线上实际配置保持一致）。

---

## 阶段 2（中风险，先观测再删除）

目标：先解除接口契约依赖，再执行数据库下线。

### 2A：接口层“软下线”（不删库）

建议新增开关（默认保留）：

- `FEATURE__EXPOSE_MESSAGE_METADATA`
- `FEATURE__EXPOSE_MESSAGE_STATS`

当关闭时：

- `message_metadata` 返回空对象或 `null`
- duration 与 `token_stats` 置空或不返回

观测周期（建议 7~14 天）：

- 前端是否出现字段缺失相关错误
- 外部调用方/报表是否依赖这些字段
- 业务指标是否异常波动

### 2B：数据库分批删除（2A 稳定后）

建议顺序：

1. `message_metadata`
2. duration 系列字段
3. `token_stats`
4. `reply_to`（最后评估）

`reply_to` 建议最后删除的原因：

- 语义上是 assistant->user 的关联键，未来可能用于追踪、重试、审计。

---

## 上线前 SQL 检查清单

```sql
-- 1) messages 总量
SELECT COUNT(*) AS total FROM messages;

-- 2) embedding 字段空值率
SELECT
  COUNT(*) FILTER (WHERE embedding_vector IS NULL) AS embedding_vector_null,
  COUNT(*) FILTER (WHERE embedding_model IS NULL OR embedding_model = '') AS embedding_model_null,
  COUNT(*) AS total
FROM messages;

-- 3) reply_to 使用率（按角色）
SELECT
  role,
  COUNT(*) AS cnt,
  COUNT(*) FILTER (WHERE reply_to IS NOT NULL AND reply_to <> '') AS reply_to_non_null
FROM messages
GROUP BY role;

-- 4) metadata 空值/空对象比例
SELECT
  COUNT(*) FILTER (WHERE message_metadata IS NULL) AS metadata_null,
  COUNT(*) FILTER (WHERE message_metadata = '{}'::jsonb) AS metadata_empty_obj,
  COUNT(*) AS total
FROM messages;

-- 5) 统计字段覆盖率
SELECT
  COUNT(*) FILTER (WHERE tool_calls_duration IS NOT NULL) AS tool_calls_duration_used,
  COUNT(*) FILTER (WHERE component_tool_calls_duration IS NOT NULL) AS component_tool_calls_duration_used,
  COUNT(*) FILTER (WHERE reasoning_duration IS NOT NULL) AS reasoning_duration_used,
  COUNT(*) FILTER (WHERE content_duration IS NOT NULL) AS content_duration_used,
  COUNT(*) FILTER (WHERE total_duration IS NOT NULL) AS total_duration_used,
  COUNT(*) FILTER (WHERE token_stats IS NOT NULL) AS token_stats_used,
  COUNT(*) AS total
FROM messages;
```

---

## 迁移实施建议

- 每一批字段独立迁移，避免大批量耦合回滚。
- 每批迁移上线后至少观察一个发布窗口。
- PR 与变更记录中明确标注：
  - 删除字段列表
  - 回滚步骤
  - 观测指标与负责人

