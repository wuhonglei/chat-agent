# Chat Agent 接口缓存方案

**创建时间**: 2026-07-14
**目标**: 降低 DB 查询压力，提升接口 QPS，减少 P50/P99 延迟

---

## 1. 现状分析

### 1.1 性能瓶颈（来自 benchmark 数据）


| 接口                                    | CDN QPS | 公网直连 QPS | 瓶颈                         |
| ------------------------------------- | ------- | -------- | -------------------------- |
| `GET /api/chat/models`                | 175     | 181      | 纯 CPU，无 DB                 |
| `GET /api/user/detail`                | 182     | 200      | PG 主键查询                    |
| `GET /api/conversation/detail`        | 170     | 189      | PG 主键查询                    |
| `GET /api/conversation/{id}/messages` | 153     | 118      | 按 conversation_id 查询 + content_blocks 序列化 |
| `GET /api/conversation/list`          | **67**  | **158**  | PG 游标分页 + 多字段排序            |
| `GET /api/health`                     | 117     | 194      | Redis PING                 |


### 1.2 现有 Redis 基础设施

- `app/core/redis.py`: 已有异步 Redis 连接池（`redis.asyncio`），max_connections=20
- 当前仅用于: SSE Stream Relay（pub/sub + stream）+ health check
- 未用于业务数据缓存

---



## 2. 缓存分层策略

```
请求 → 内存缓存（L1） → Redis 缓存（L2） → PostgreSQL（DB）
          命中 ↓              命中 ↓              ↓
        直接返回            直接返回         查询后回填缓存
```



### 2.1 L1 — 进程内存缓存（cachetools.TTLCache）

**适用场景**: 全局共享、极少变化、无用户差异的数据


| 缓存项                    | TTL  | 容量  | 说明                         |
| ---------------------- | ---- | --- | -------------------------- |
| `/api/chat/models` 响应  | 300s | 1   | 模型列表来自配置文件，重启/Nacos 热更新时才变 |
| `/api/health` Redis 状态 | 5s   | 1   | 避免每请求 PING Redis           |


**不适用**: 用户及会话维度数据。8 个 worker 的 L1 互不共享，写请求只能清理当前
worker，其他 worker 会在 TTL 内继续返回旧值。因此 `user/detail` 与
`conversation/detail` 均只使用 L2。

### 2.2 L2 — Redis 缓存

**适用场景**: 用户维度数据、读多写少、可容忍短暂不一致


| 缓存项                                   | TTL | Key 格式                                       | 失效时机                   |
| ------------------------------------- | --- | -------------------------------------------- | ---------------------- |
| `GET /api/user/detail`                | 60s | `cache:user:{user_id}`                       | 用户信息更新时删除              |
| `GET /api/conversation/detail`        | 30s | `cache:conv:{conv_id}`                       | 对话或最后消息时间更新、删除时删除 |
| `GET /api/conversation/list`          | 10s | `cache:conv_list:{user_id}:{cursor}:{limit}` | 新建/删除/更新对话或消息时删除该用户所有列表缓存 |
| `GET /api/conversation/{id}/messages` | 15s | `cache:msg:{conv_id}`                        | 消息新增、完成、停止、失败、删除或反馈时删除 |


**不缓存的接口**:

- `POST /api/chat/stream` — 写操作 + SSE 流式，不可缓存
- `POST/PUT/DELETE` 写操作 — 只负责删除相关读缓存（cache invalidation）

`conversation/list` 的首页 cursor 固定编码为空字符串，key 示例为
`cache:conv_list:{user_id}::{limit}`，禁止混用 `None`、`null` 等表示，确保前缀失效
可以覆盖所有分页 key。

---



## 3. 代码结构设计



### 3.1 新增文件

```
backend/app/core/cache.py          # 缓存基础设施（L1 内存 + L2 Redis 读写封装）
```



### 3.2 `cache.py` 核心接口

```python
"""缓存层：L1 进程内存 + L2 Redis"""

from __future__ import annotations

import json
from typing import Any

from cachetools import TTLCache

from app.core.redis import get_redis
from app.utils.logger import logger

# ── L1: 仅用于 models / health ──
_l1: dict[str, TTLCache] = {}


def _get_l1(namespace: str, maxsize: int, ttl: float) -> TTLCache:
    if namespace not in _l1:
        _l1[namespace] = TTLCache(maxsize=maxsize, ttl=ttl)
    return _l1[namespace]


def l1_get(namespace: str, key: str, *, maxsize: int = 128, ttl: float = 300) -> Any | None:
    return _get_l1(namespace, maxsize, ttl).get(key)


def l1_set(
    namespace: str,
    key: str,
    value: Any,
    *,
    maxsize: int = 128,
    ttl: float = 300,
) -> None:
    _get_l1(namespace, maxsize, ttl)[key] = value


def l1_delete(namespace: str, key: str | None = None) -> None:
    """key=None 清空整个 namespace。"""
    if key is None:
        _l1.pop(namespace, None)
    elif namespace in _l1:
        _l1[namespace].pop(key, None)


# ── L2: 用户及会话维度数据 ──
L2_DEFAULT_TTL = 60
MAX_CACHE_VALUE_BYTES = 512 * 1024


def _record_cache_event(event: str, namespace: str) -> None:
    """首期使用结构化日志；后续可替换为 metrics counter。"""
    logger.info(event, cache_namespace=namespace)


async def l2_get(key: str, *, namespace: str) -> Any | None:
    try:
        raw = await get_redis().get(key)
        value = None if raw is None else json.loads(raw)
    except Exception:
        _record_cache_event("cache_l2_error", namespace)
        raise
    if value is None:
        _record_cache_event("cache_miss", namespace)
        return None
    _record_cache_event("cache_hit", namespace)
    return value


async def l2_set(
    key: str,
    value: Any,
    *,
    namespace: str,
    ttl: int = L2_DEFAULT_TTL,
    max_bytes: int | None = None,
) -> bool:
    raw = json.dumps(value, ensure_ascii=False, default=str).encode()
    if max_bytes is not None and len(raw) > max_bytes:
        _record_cache_event("cache_skip_oversize", namespace)
        return False
    try:
        await get_redis().set(key, raw, ex=ttl)
    except Exception:
        _record_cache_event("cache_l2_error", namespace)
        raise
    return True


async def l2_delete_pattern(pattern: str, *, namespace: str) -> int:
    """SCAN 分批匹配并用 UNLINK 异步释放 value 内存。"""
    try:
        redis = get_redis()
        deleted = 0
        batch: list[str] = []
        async for key in redis.scan_iter(match=pattern, count=100):
            batch.append(key)
            if len(batch) < 100:
                continue
            deleted += await redis.unlink(*batch)
            batch.clear()
        if batch:
            deleted += await redis.unlink(*batch)
    except Exception:
        _record_cache_event("cache_l2_error", namespace)
        raise
    if deleted:
        _record_cache_event("cache_invalidate", namespace)
    return deleted


async def l2_delete(key: str, *, namespace: str) -> None:
    try:
        await get_redis().unlink(key)
    except Exception:
        _record_cache_event("cache_l2_error", namespace)
        raise
    _record_cache_event("cache_invalidate", namespace)
```

本期不捕获 Redis 异常并回落 DB；`cache_l2_error` 只提供观测，fail-open 留到风险加固
迭代。

### 3.3 Service 层接入方式（以 user/detail 为例）

```python
# app/services/user/user_db.py
async def get_or_load_user_detail(self, user_id: str) -> dict[str, Any] | None:
    cached = await l2_get(f"cache:user:{user_id}", namespace="user")
    if cached is not None:
        return cached

    user = self.get_user(user_id)
    if not user:
        return None

    data = user.model_dump(mode="json")
    await l2_set(
        f"cache:user:{user_id}",
        data,
        namespace="user",
        ttl=60,
    )
    return data


# app/api/user.py — handler 只负责协议与鉴权
user = await UserDbService(db).get_or_load_user_detail(token_info.user_id)
if not user:
    raise HTTPException(status_code=401, detail="用户不存在")
return ApiResponse.success(data=user)
```

`conversation/detail` 与 `messages` 采用同样的 service 层 get-or-load 模式。缓存值
统一使用 `{"owner_user_id": user_id, "response": data}` envelope；命中时先比较
`owner_user_id` 与 `token_info.user_id`，只将 `response` 返回给客户端。未命中时查询
DB 并验证 `conversation.user_id` 后再回填。这样命中缓存不需要额外查 DB，也不会绕过
ownership check。

消息回填时传入体量上限：

```python
await l2_set(
    f"cache:msg:{conversation_id}",
    {"owner_user_id": user_id, "response": data},
    namespace="msg",
    ttl=15,
    max_bytes=MAX_CACHE_VALUE_BYTES,
)
```

### 3.4 统一缓存失效接口

```python
def conversation_list_key(user_id: str, cursor: str | None, limit: int) -> str:
    normalized_cursor = cursor or ""
    return f"cache:conv_list:{user_id}:{normalized_cursor}:{limit}"


async def invalidate_user(user_id: str) -> None:
    await l2_delete(f"cache:user:{user_id}", namespace="user")


async def invalidate_conversation(conversation_id: str, user_id: str) -> None:
    await l2_delete(f"cache:conv:{conversation_id}", namespace="conv")
    await l2_delete_pattern(
        f"cache:conv_list:{user_id}:*",
        namespace="conv_list",
    )


async def invalidate_messages(conversation_id: str) -> None:
    await l2_delete(f"cache:msg:{conversation_id}", namespace="msg")
```

失效函数由实际写入数据的 service / chat orchestrator 调用，而不是散落在 API handler。
这样 `POST /chat/stream`、stop、FAILED 等不经过 conversation/message 写接口的路径也
不会遗漏。

### 3.5 Nacos 热更新清理 models L1

`app/core/config.py` 的 `reload_settings()` 在替换 settings 后清理 models namespace：

```python
from app.core.cache import l1_delete


def reload_settings() -> None:
    # ...重新加载并替换 settings...
    l1_delete("models")
```

每个 worker 接收 Nacos listener 更新并清理自身 L1；重启仍是最终兜底。

### 3.6 可观测性

首期至少记录以下结构化事件，并带 `cache_namespace`：

- `cache_hit` / `cache_miss`
- `cache_invalidate`
- `cache_l2_error`
- `cache_skip_oversize`

按 `user`、`conv`、`conv_list`、`msg`、`models`、`health` 聚合命中率和错误率。验收时
将这些数据与 PostgreSQL 查询次数、连接占用和接口 P99 一起对照。

---



## 4. 各接口缓存方案详述



### 4.1 `GET /api/chat/models`（内存缓存）

```
缓存层: L1 only
TTL: 300s（5分钟）
Key: "global"（全局唯一）
失效: Nacos 配置热更新时调用 l1_delete("models")
原因: 模型列表来自 settings，所有用户看到相同内容，重启即刷新
预期收益: QPS 175 → 200+（消除 list_text_generation_models() 调用开销）
```



### 4.2 `GET /api/user/detail`（Redis）

```
缓存层: L2 only
TTL: 60s
Key: cache:user:{user_id}
失效: PUT /api/user/update_info 时删除
原因: 用户信息读多写少（每次页面加载都调用），主键查询虽快但频率极高
预期收益: QPS 182 → 200+（消除 DB 主键查询）
```



### 4.3 `GET /api/conversation/detail`（Redis）

```
缓存层: L2 only
TTL: 30s
Key: cache:conv:{conversation_id}
失效: PUT /update, PUT /activate, DELETE /delete, POST /chat/stream,
      PUT /message/feedback 时删除
权限: 缓存命中须校验 envelope.owner_user_id == token_info.user_id
原因: 对话详情在消息列表页和聊天页都会被查询
预期收益: QPS 170 → 190+
```



### 4.4 `GET /api/conversation/list`（Redis）

```
缓存层: L2 only（因为是用户维度 + 分页参数，L1 命中率低）
TTL: 10s（短 TTL，因为对话列表变化较频繁）
Key: cache:conv_list:{user_id}:{cursor or ""}:{limit}
     首页示例: cache:conv_list:{user_id}::{limit}
失效: POST /register, PUT /update, PUT /activate, DELETE /delete 时
      以及 POST /chat/stream、PUT /message/feedback 时
      删除 cache:conv_list:{user_id}:*（SCAN + UNLINK 批量删除）
原因: 这是最慢的接口（67 QPS），游标分页查询涉及多字段排序
预期收益: QPS 67 → 120+（DB 查询是主要瓶颈）
```



### 4.5 `GET /api/conversation/{id}/messages`（Redis）

```
缓存层: L2 only（消息列表可能很大，L1 内存占用高）
TTL: 15s
Key: cache:msg:{conversation_id}
失效: POST /chat/stream（新消息/完成/失败）, POST /chat/stream/stop,
      DELETE /message, PUT /feedback 时删除
权限: 缓存查询前先完成 token 鉴权；命中时校验 envelope.owner_user_id，未命中时
      校验 DB conversation.user_id，任何路径都不能跳过归属校验
体量: 序列化结果超过 512 KiB 时跳过缓存
原因: 按 conversation_id 查询的结果集及 content_blocks 序列化开销较高，
      且消息变化频率也高
预期收益: QPS 153 → 180+
```



### 4.6 `GET /api/health`（内存缓存）

```
缓存层: L1 only
TTL: 5s
Key: "redis_ping"
失效: 自动过期
原因: 每次 PING Redis 的开销可忽略，但压测时频率极高
预期收益: QPS 117 → 190+（消除 Redis PING）
```

---



## 5. 缓存失效总览

```
写操作                  失效的缓存
─────────────────────────────────────────────
POST /conversation/register  → L2: cache:conv_list:{user_id}:*
PUT  /conversation/update    → L2: cache:conv:{id}, cache:conv_list:{user_id}:*
PUT  /conversation/activate  → L2: cache:conv:{id}, cache:conv_list:{user_id}:*
DELETE /conversation/delete  → L2: cache:conv:{id}, cache:conv_list:{user_id}:*, cache:msg:{id}
POST /chat/stream            → L2: cache:msg:{conv_id}, cache:conv:{conv_id}, cache:conv_list:{user_id}:*
POST /chat/stream/stop       → L2: cache:msg:{conv_id}
stream STOPPED/FAILED        → L2: cache:msg:{conv_id}
DELETE /message/delete       → L2: cache:msg:{conv_id}
PUT  /message/feedback       → L2: cache:msg:{conv_id}, cache:conv:{conv_id}, cache:conv_list:{user_id}:*
PUT  /user/update_info       → L2: cache:user:{user_id}
```

上述失效在数据写入成功后由 service / orchestrator 调用。删除会话时先取得
`user_id`，再删除实体并失效三个 namespace。

---



## 6. 依赖变更

```toml
# pyproject.toml 新增
"cachetools>=5.3.0",
```

仅新增 `cachetools`（纯 Python，无编译依赖）。Redis 客户端 `redis>=5.0.0` 已有。

---



## 7. 预期效果


| 接口                                | 当前 QPS | 缓存后预估 QPS | 提升       |
| --------------------------------- | ------ | --------- | -------- |
| `/api/chat/models`                | 175    | **200+**  | +15%     |
| `/api/user/detail`                | 182    | **200+**  | +10%     |
| `/api/conversation/detail`        | 170    | **190+**  | +12%     |
| `/api/conversation/list`          | **67** | **120+**  | **+79%** |
| `/api/conversation/{id}/messages` | 153    | **180+**  | +18%     |
| `/api/health`                     | 117    | **190+**  | +62%     |


**最大收益**: `conversation/list`（当前瓶颈）预计提升 ~80%，`health` 预计提升 ~60%。

以上 QPS 是容量规划假设，不作为上线验收承诺。现有 benchmark 表明外网 RTT 与 TLS
仍是端到端主要瓶颈，缓存主要减少 DB/CPU 压力。

### 7.1 验收指标

使用同一数据集和并发参数进行缓存前后对照：

1. 本地 gunicorn / 内网请求的 P50、P99
2. PostgreSQL 查询次数、QPS 与连接池占用
3. 各 namespace 的缓存命中率、失效次数、L2 错误率
4. `messages` 超限跳过次数与 Redis 内存变化
5. CDN QPS 仅作参考，不作为缓存是否有效的唯一判断

---



## 8. 风险与注意事项

1. **缓存一致性**: 采用 Cache-Aside 模式，写操作主动删除缓存，TTL 兜底防不一致
2. **缓存穿透**: 本期不做负缓存；不存在的数据仍会查询 DB
3. **缓存雪崩**: 本期使用固定 TTL，不实现随机抖动
4. **Redis 故障**: 本期不实现 fail-open，先通过 `cache_l2_error` 观测
5. **并发回填**: 本期不加锁或版本号，依赖主动失效与 TTL 兜底
6. **内存占用**: L1 仅缓存 models（约 1KB）和 health 状态，可忽略
7. **消息体量**: messages 序列化结果超过 512 KiB 时跳过缓存
8. **权限校验**: conversation detail/messages 在缓存命中时仍验证会话归属
9. **Redis 序列化**: 使用 `json.dumps(default=str)` 处理 datetime 等类型
10. **conversation/list 的 SCAN 删除**: 使用 `SCAN + UNLINK`，不使用 `KEYS`

本期仅依赖主动失效 + TTL 兜底；TTL jitter、负缓存、fail-open 与并发回填保护另立
风险加固迭代，待实际体验和观测数据确认后再实施。
