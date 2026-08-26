# 会话搜索接口优化方案

**接口**：`GET /api/conversation/search`
**当前延迟**：1.88s（P50）
**瓶颈**：`content_blocks` 是 JSON 列，ILIKE 前要 `cast(content_blocks, String)` 全表序列化再匹配，无法走索引。

---

## Step 1：提取纯文本冗余列

**目标**：省掉 JSON 序列化开销，延迟预期 200-500ms。

### 1.1 改动点

新增 `messages.content_text` 列，存 `content_blocks` 中的纯文本内容（拼接所有 TextBlock）。

```python
# app/models/message_db.py
content_text: str | None = Field(
    default=None,
    sa_column=Column(Text, nullable=True, index=True),
)
```

### 1.2 同步机制

写入/更新 `content_blocks` 时，触发器自动提取纯文本：

```sql
CREATE OR REPLACE FUNCTION sync_message_content_text() RETURNS trigger AS $$
DECLARE
    extracted text;
BEGIN
    -- 从 JSON content_blocks 中提取所有 TextBlock 的 text 字段
    SELECT string_agg(value->>'text', ' ')
    INTO extracted
    FROM jsonb_array_elements(NEW.content_blocks::jsonb)
    WHERE value->>'type' = 'text';

    NEW.content_text := extracted;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_sync_content_text
    BEFORE INSERT OR UPDATE OF content_blocks ON messages
    FOR EACH ROW EXECUTE FUNCTION sync_message_content_text();
```



### 1.3 回填历史数据

```sql
UPDATE messages
SET content_text = (
    SELECT string_agg(value->>'text', ' ')
    FROM jsonb_array_elements(content_blocks::jsonb)
    WHERE value->>'type' = 'text'
)
WHERE content_blocks IS NOT NULL;
```



### 1.4 查询改造

```python
# app/services/conversation/conversation_db.py
# 替换：
content_text = sa_cast(cast(Any, MessageDb.content_blocks), String)
# 为：
content_text = cast(Any, MessageDb.content_text)
```



### 1.5 Alembic 迁移

```bash
uv run alembic revision --autogenerate -m "add content_text to messages"
```

迁移内容：加列 + 触发器 + 回填。

### 1.6 预期效果


| 指标   | 改造前              | 改造后                        |
| ---- | ---------------- | -------------------------- |
| 延迟   | 1.88s            | 200-500ms                  |
| 扫描方式 | JSON 序列化 + ILIKE | 纯文本 ILIKE                  |
| 索引   | 无                | B-tree on content_text（可选） |


---



## Step 2：tsvector 中文分词全文搜索

**目标**：走 GIN 索引，延迟预期 50ms 以内。

### 2.1 前置依赖

安装 `zhparser` 扩展：

```sql
CREATE EXTENSION IF NOT EXISTS zhparser;
CREATE TEXT SEARCH CONFIGURATION zhcfg (PARSER = zhparser);
ALTER TEXT SEARCH CONFIGURATION zhcfg ADD MAPPING FOR n,v,a,i,e,l WITH simple;
```

Docker 镜像需包含 zhparser（或在 Dockerfile 中安装）。

### 2.2 改动点

新增 `messages.content_tsv` 列：

```python
# 使用 SQLAlchemy 原生列类型
from sqlalchemy.dialects.postgresql import TSVECTOR

content_tsv = Field(
    sa_column=Column(TSVECTOR, nullable=True),
)
```



### 2.3 触发器

在 Step 1 的触发器基础上增加 tsvector 同步：

```sql
CREATE OR REPLACE FUNCTION sync_message_content_text() RETURNS trigger AS $$
DECLARE
    extracted text;
BEGIN
    -- Step 1: 提取纯文本
    SELECT string_agg(value->>'text', ' ')
    INTO extracted
    FROM jsonb_array_elements(NEW.content_blocks::jsonb)
    WHERE value->>'type' = 'text';

    NEW.content_text := extracted;

    -- Step 2: 生成 tsvector
    IF extracted IS NOT NULL THEN
        NEW.content_tsv := to_tsvector('zhcfg', extracted);
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
```



### 2.4 索引

```sql
CREATE INDEX idx_messages_content_tsv ON messages USING GIN(content_tsv);
```



### 2.5 查询改造

```python
# 替换 ILIKE 为 tsvector 查询
from sqlalchemy import func

content_tsv_column = cast(Any, MessageDb.content_tsv)
ts_query = func.to_tsquery('zhcfg', ' & '.join(keyword.split()))

message_match_exists = (
    select(MessageDb.id)
    .where(MessageDb.conversation_id == ConversationDb.id)
    .where(role_column.in_(["user", "assistant"]))
    .where(MessageDb.status == "done")
    .where(content_tsv_column.op("@@")(ts_query))
    .exists()
)
```



### 2.6 预期效果


| 指标    | Step 1     | Step 2             |
| ----- | ---------- | ------------------ |
| 延迟    | 200-500ms  | 10-50ms            |
| 中文分词  | 无（子串匹配）    | 有（zhparser 分词）     |
| 相关度排序 | 无          | `ts_rank()` 按相关度排序 |
| 索引类型  | B-tree（可选） | GIN                |




### 2.7 相关度排序（可选）

```python
rank = func.ts_rank(content_tsv_column, ts_query)
data_stmt = data_stmt.order_by(rank.desc(), last_message_created_at_column.desc())
```

---



## 实施节奏


| 阶段     | 内容                              | 耗时    | 风险                       |
| ------ | ------------------------------- | ----- | ------------------------ |
| Step 1 | 加列 + 触发器 + 回填 + 查询改造            | 0.5 天 | 低（触发器出错可回滚）              |
| Step 2 | 安装 zhparser + tsvector + GIN 索引 | 1 天   | 中（zhparser Docker 镜像需验证） |


建议先上线 Step 1 验证延迟改善，再按需推进 Step 2。