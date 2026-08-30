# 会话搜索（当前实现）

**接口**：`GET /api/conversation/search`  
**最后核对**：2026-08-30（对照 `ConversationDbService`、Alembic `h1i2j3k4l5m6` / `i2j3k4l5m6n7`）

侧栏 / ⌘K 搜索的后端契约见 `docs/会话管理.md`。本文说明索引、查询语义与运维约束。

## 1. 意图

旧实现把 `content_blocks` JSON `cast` 成字符串再 `ILIKE`，无法走索引，P50 约 1.9s。现网拆成两步：

1. **纯文本列** `messages.content_text`：只拼 `type=text` 的 TextBlock，写入与触发器双写。
2. **中文全文检索** `messages.content_tsv`：`to_tsvector('zhcfg', content_text)` + GIN，查询用 `plainto_tsquery('zhcfg', q)`。

标题仍走 `ILIKE`（短字段、需要子串），**不**进 tsvector。

## 2. 数据流

```text
写入 / 更新 content_blocks
  ├─ 应用层：MessageDbService 同时写 content_text
  └─ 触发器 trg_sync_content_text（BEFORE INSERT OR UPDATE OF content_blocks）
       ├─ 去掉 JSON 文本中的 \u0000 转义（PG text 不能含 NUL，->> 会失败）
       ├─ 只聚合 type=text 的 text
       ├─ content_text := extracted
       └─ content_tsv := to_tsvector('zhcfg', extracted)   # 空则 NULL
```

应用层写 `content_text` 是为了 SQLite 单测与触发器未挂上的环境仍可搜；生产以触发器为准同步 `content_tsv`。

| 列 | 类型 | 谁维护 | 用途 |
|----|------|--------|------|
| `content_blocks` | JSON | 业务写入 | 消息主体 |
| `content_text` | Text | 应用 + 触发器 | 搜索冗余 / 方言回退 |
| `content_tsv` | TSVECTOR（SQLite 映射为 Text） | 仅 PG 触发器 | `@@` 全文匹配 |

索引：`idx_messages_content_tsv`（`GIN (content_tsv)`，迁移里 `CREATE INDEX CONCURRENTLY`）。

## 3. 查询语义

```python
# PostgreSQL
content_tsv @@ plainto_tsquery('zhcfg', keyword)

# 非 PostgreSQL（pytest / SQLite）
content_text ILIKE '%' || escaped(keyword) || '%'
```

约束（与代码一致）：

- 只搜当前用户、`is_active=true` 的会话。
- 消息：`role in (user, assistant)` 且 `status=done`。
- 同一会话一行；标题子串命中优先，否则取该会话**最早**一条正文命中。
- 列表排序：`(last_message_created_at DESC, id DESC)`，没有 `ts_rank`。
- `q`：1–200 字符；服务层对 strip 后空串返回空页。
- `ILIKE` 会转义用户输入中的 `\` `%` `_`。

`plainto_tsquery` 会按 `zhcfg` 分词后再 AND。因此：

- 中文词可以命中，不必整句连续子串。
- 极短或未进词典的碎片可能比旧 ILIKE **更严**（标题 ILIKE 仍能兜住标题党）。
- snippet 仍按原始 `q`（或首个空白 token）做子串切片；分词命中但对不上原文时，snippet 退回正文前约 80 字。

不可搜索：image / pdf / markdown 附件块、tool_use / tool_result、`pending`/`failed` 消息、其它用户会话、草稿（`is_active=false`）。

## 4. 扩展与镜像

迁移 `i2j3k4l5m6n7` 会：

1. `CREATE EXTENSION IF NOT EXISTS zhparser`（无权限时忽略；扩展文件不存在则 **硬失败**）
2. 确认 `pg_ts_parser.prsname = zhparser`
3. `CREATE TEXT SEARCH CONFIGURATION zhcfg (PARSER = zhparser)`（若不存在）
4. `ALTER TEXT SEARCH CONFIGURATION zhcfg ADD MAPPING FOR n,v,a,i,e,l WITH simple`
5. 加列、替换触发器、回填 `content_tsv`、并发建 GIN

本地 / 部署必须用本仓库镜像 `chat-agent-postgres:pg18-zhparser`（`docker/postgres/Dockerfile`：`pgvector/pgvector:pg18` + SCWS + 本地 `zhparser` 源码）。

```bash
# 换镜像（勿 down -v，会删 postgres_data）
docker compose build postgres && docker compose up -d --force-recreate postgres
```

排障：

| 现象 | 处理 |
|------|------|
| 迁移报 `zhparser` 不可用 | 先换上述镜像再 `alembic upgrade head` |
| 扩展装了但 `pg_ts_parser` 无 zhparser | `CREATE EXTENSION zhparser;` |
| 新消息搜不到 | 看 `content_text` / `content_tsv` 是否随 `content_blocks` 更新；触发器是否还在 |
| 历史消息正文空 | 触发器只处理 text 块；旧数据应已在迁移里回填，可对缺行重跑 `to_tsvector('zhcfg', content_text)` |

downgrade 会还原「只同步 `content_text`」的触发器并丢 `content_tsv`，**不会** drop `zhcfg` / `zhparser`。

## 5. 源码索引

| 主题 | 路径 |
|------|------|
| 查询 / snippet | `backend/app/services/conversation/conversation_db.py` |
| 模型列 | `backend/app/models/message_db.py` |
| 应用层写 `content_text` | `backend/app/services/message/message_db.py` |
| API / 校验 | `backend/app/api/conversation.py`、`ConversationSearchRequest` |
| 纯文本列 + 触发器 | `backend/alembic/versions/h1i2j3k4l5m6_add_content_text_to_messages.py` |
| zhparser + GIN | `backend/alembic/versions/i2j3k4l5m6n7_add_content_tsv_zhparser.py` |
| 单测（ILIKE 回退） | `backend/tests/services/conversation/test_conversation_search.py` |
| 前端 ⌘K | `frontend/docs/conversation.md` |

## 6. 演进备注

Step 1（纯文本列 + ILIKE）与 Step 2（zhparser + GIN）均已合入主干。规划稿里的 `to_tsquery` + 空格拼 `&`、以及 `ts_rank` 排序**没有**落地；现网查询是 `plainto_tsquery`，排序仍按会话最近消息时间。
