# 接口缓存现网实现与运维

**最后核对**：2026-07-19  
**目标**：减少低成本、重复读取带来的开销，同时避免远程 Redis 往返拖慢会话热路径。

本文档描述当前代码中的缓存行为。历史方案曾为会话详情、会话列表和消息列表增加
L2 Redis 缓存，但压测确认收益为负后已移除；不要按旧方案恢复这些缓存。

## 1. 当前架构

```text
GET /api/chat/models ────────────────→ L1 进程内缓存 ─→ 配置
GET /api/health ─────────────────────→ L1 进程内缓存 ─→ Redis PING
GET /api/user/detail ────────────────→ L2 Redis ─────→ PostgreSQL
会话详情 / 会话列表 / 消息列表 ───────────────────────→ PostgreSQL
```

实现入口：

- L1：`backend/app/core/local_cache.py`
- L2：`backend/app/core/cache.py`
- 用户详情接入：`backend/app/services/user/user_db.py`
- L1 接入：`backend/app/api/models.py`、`backend/app/api/health.py`
- 配置：`backend/app/schemas/config.py` 的 `CacheConfig`

### 1.1 生效中的缓存

| 接口 | 层级 | Key | TTL | 回源 |
|------|------|-----|-----|------|
| `GET /api/chat/models` | L1 | namespace `models` / key `global` | 300 秒 | 当前模型配置 |
| `GET /api/health` 的 Redis 状态 | L1 | namespace `health` / key `redis_ping` | 5 秒 | `ping_redis()` |
| `GET /api/user/detail` | L2 | `cache:user:{user_id}` | 默认 60 秒 | PostgreSQL 用户表 |

L1 使用 `cachetools.TTLCache`，每个 worker 各有一份，不能用于用户或会话数据。
模型配置热更新时，`reload_settings()` 会清空当前 worker 的 `models` namespace；
进程重启也会清空全部 L1 数据。

用户详情缓存直接保存 `UserDb.model_dump(mode="json")`。更新资料、短信或微信登录、
登出成功后会在数据库提交完成后删除 `cache:user:{user_id}`。

### 1.2 明确不缓存的路径

以下接口直接查询 PostgreSQL：

- `GET /api/conversation/detail/{conversation_id}`
- `GET /api/conversation/list`
- `GET /api/conversation/{conversation_id}/messages`

`invalidate_conversation_list()`、`invalidate_conversation()`、
`invalidate_messages()` 和 `invalidate_conversation_state()` 目前是兼容现有写路径的
空操作。调用它们不会删除 Redis key，也不表示对应读接口仍有缓存。

## 2. L2 fail-open 行为

L2 只是一层可选加速，Redis 故障不能阻断业务读取：

1. `GET`、`SET`、`UNLINK` 和分批 `SCAN + UNLINK` 均受
   `cache.operation_timeout_seconds` 限制。
2. Redis 异常或超时记录 `cache_l2_error`，不会继续向调用方抛出。
3. `l2_get()` 返回 `None`，用户详情服务随即回源 PostgreSQL。
4. `l2_set()` 返回 `false`；回源结果仍正常返回，只是本次不写缓存。
5. `l2_delete()` / `l2_delete_pattern()` 返回 `0`；后续由 TTL 兜底。

默认操作超时为 `0.5` 秒，短于 Redis 连接池为 SSE `XREAD BLOCK` 设置的 socket
超时，避免缓存请求在连接池压力下长期等待。

## 3. 配置

配置可由 Nacos 或环境变量提供。环境变量使用双下划线映射嵌套字段：

```dotenv
CACHE__USER_DETAIL_TTL_SECONDS=60
CACHE__OPERATION_TIMEOUT_SECONDS=0.5
```

当前实际消费的配置：

| 配置项 | 默认值 | 用途 |
|--------|--------|------|
| `cache.user_detail_ttl_seconds` | `60` | 用户详情 L2 TTL |
| `cache.operation_timeout_seconds` | `0.5` | 单次 L2 操作超时 |

`CacheConfig` 中的 `conversation_detail_ttl_seconds`、
`conversation_list_ttl_seconds`、`messages_ttl_seconds` 和
`max_value_bytes` 是已移除会话 L2 方案遗留的兼容字段，当前业务路径不读取它们。
修改这些值不会改变会话或消息接口行为。

L1 的 TTL 与容量固定在 `local_cache.py`，目前不能通过 Nacos 或环境变量修改。

## 4. 可观测性与排障

缓存日志均带 `cache_level` 和 `cache_namespace`：

| 事件 | 级别 | 含义 |
|------|------|------|
| `cache_hit` / `cache_miss` | debug | L1/L2 命中或未命中 |
| `cache_invalidate` | info | L1/L2 删除完成；`deleted=0` 也会记录 |
| `cache_skip_oversize` | info | 调用方设置 `max_bytes` 且值超限 |
| `cache_l2_error` | error | Redis 操作异常或超过操作超时 |

`cache_l2_error` 还包含 `cache_operation`、`cache_namespace`、
`error` 和 `error_type`。常见操作值为 `get`、`set`、`unlink`、
`scan_unlink`。

### Redis 不可用

预期现象：

- `/api/health` 最多在 5 秒 L1 TTL 后显示 `redis: unavailable`；
- `/api/user/detail` 记录 `cache_l2_error` 后回源数据库；
- SSE 断线续流、跨 worker stop 和 turn 幂等依赖 Redis，不属于本缓存层的
  fail-open 范围，详见 `docs/会话管理.md`。

若 `cache_l2_error` 持续出现：

1. 检查 `/api/health` 的 `data.redis`；
2. 按 `cache_operation` 区分连接/读取与失效问题；
3. 检查 Redis 连接池压力和网络延迟；
4. 不要通过增大 `operation_timeout_seconds` 掩盖连接池耗尽，否则缓存等待会与
   PostgreSQL 回源时间叠加。

## 5. 为什么会话 L2 被移除

2026-07-18 压测显示，远程 Redis 往返、连接池等待和 JSON 序列化成本高于当前
PostgreSQL 查询收益：

- 会话详情的主键查询本身约为毫秒级；
- 会话列表在 Redis 超时时还要继续查询数据库，延迟发生叠加；
- 消息列表 JSON 较大，序列化与网络传输成本明显；
- 高并发下出现 `cache_l2_error (TimeoutError)` 和 Gunicorn worker timeout。

移除会话详情、会话列表和消息列表 L2 后，测试中的 Non-2xx 恢复为 0，会话列表与
消息列表 QPS 明显恢复。完整数据和测试条件见
`docs/benchmark/2026-07-12_qps_benchmark.md` 的 8.6.5–8.6.6 节。

因此，新增缓存前必须在与生产相同的 Redis 网络拓扑下测量：

1. 接口 P50/P99 和错误率；
2. PostgreSQL 查询次数与连接占用；
3. Redis 连接池等待和 `cache_l2_error`；
4. 序列化大小与 CPU；
5. 缓存命中时与超时回源时的差异。

只有实际收益覆盖远程缓存成本时，才应扩展 L2 范围。
