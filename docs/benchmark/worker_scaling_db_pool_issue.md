# Worker 扩容引发的数据库连接池问题排查与解决

**日期**: 2026-07-12
**问题**: 将 Gunicorn workers 从 1 提升到 8 后，QPS 反而下降 70%

---

## 1. 问题现象

### 优化前（WORKERS=1）

| 接口 | QPS | P50 | P95 | P99 |
|------|-----|-----|-----|-----|
| `/api/health` | 137.84 | 281ms | 660ms | 971ms |
| `/api/user/detail` | 139.91 | 257ms | 717ms | 997ms |
| `/api/conversation/list` | 54.32 | 657ms | 2147ms | 3844ms |

### 优化后（WORKERS=8）— 反而变慢

| 接口 | QPS | P50 | P95 | P99 |
|------|-----|-----|-----|-----|
| `/api/health` | 38.62 ⬇️ | 1735ms | 4862ms | 9831ms |
| `/api/user/detail` | 46.50 ⬇️ | 1449ms | 4585ms | 6203ms |
| `/api/conversation/list` | 42.80 ⬇️ | 1718ms | 5017ms | 8388ms |

**结论**: 多 worker 反而导致性能严重下降。

---

## 2. 根因分析

### 2.1 连接池配置

```python
# backend/app/core/db.py (原始配置)
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    pool_size=20,      # 常驻连接数
    max_overflow=30,   # 最大溢出连接数
    pool_pre_ping=True,
    pool_recycle=300,
)
```

### 2.2 连接数计算

```
每个 worker 最大连接数 = pool_size + max_overflow = 20 + 30 = 50
8 workers × 50 = 400 个连接
PostgreSQL 默认 max_connections = 100
```

### 2.3 问题机制

```
请求 → Worker A → 尝试获取 DB 连接
                    │
                    ▼
              连接池已满（100 连接上限被其他 worker 占用）
                    │
                    ▼
              等待可用连接（阻塞）
                    │
                    ▼
              超时或极慢响应
```

大量请求在等待数据库连接，导致：
- 并发越高，竞争越激烈
- 延迟急剧上升
- 部分请求超时失败

---

## 3. 解决方案对比

| 优先级 | 方案 | 复杂度 | 效果 | 适用阶段 |
|--------|------|--------|------|----------|
| **①** | 减少单 worker 连接池配置 | ⭐ 改一行代码 | 立竿见影 | **当前已执行** |
| **②** | 调大 PG max_connections | ⭐⭐ 重启 PG | 兜底保障 | 立即执行 |
| **③** | 使用 PgBouncer | ⭐⭐⭐⭐ 部署新组件 | 长期最优 | 规模扩大时 |

### ① 减少单 worker 连接池配置（已执行）

**改动**:

```python
# backend/app/core/db.py (优化后)
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    pool_size=5,       # 从 20 降到 5
    max_overflow=7,    # 从 30 降到 7
    pool_pre_ping=True,
    pool_recycle=300,
)
```

**计算**:

```
每个 worker: 5 + 7 = 12 连接
8 workers: 12 × 8 = 96 < PG 默认 100
```

**优点**:
- 成本最低，一行代码改动
- 立即生效，无需重启数据库
- 治本：从源头控制连接数

---

### ② 调大 PG max_connections

**当前状态**:

```
应用: 96 连接
管理工具/监控/备份: 至少 5-10 个
PG 默认: 100
余量: 仅 4 个 ⚠️ 太紧
```

**建议**: 设置为 200

```bash
# 查看当前值
sudo docker exec chat-agent-postgres psql -U postgres -c "SHOW max_connections;"

# 修改
sudo docker exec chat-agent-postgres psql -U postgres -c "ALTER SYSTEM SET max_connections = 200;"
sudo docker restart chat-agent-postgres
```

**内存开销**:

| max_connections | 额外内存 |
|-----------------|----------|
| 100 | ~1GB |
| 200 | ~2GB |
| 300 | ~3GB |

服务器内存 ≥8GB 时，设 200 没问题。

---

### ③ 使用 PgBouncer（长期方案）

```
应用 (96 连接) ──► PgBouncer ──► PostgreSQL (只需 20-30 连接)
```

**适用场景**:
- 多个服务连同一个 PG
- workers > 16
- 需要极致的连接复用

**当前阶段**: 不需要，① + ② 已足够。

---

## 4. 连接池参数详解

### pool_size（常驻连接数）

连接池保持的常驻连接数量，请求来了直接复用。

```
┌─────────────────────┐
│      连接池          │
│  [连接1] [连接2]     │
│  [连接3] [连接4]     │
│  [连接5]             │  ← 常驻，不关闭
└─────────────────────┘
```

类比：餐厅固定雇佣 5 个服务员，随时待命。

---

### max_overflow（临时连接数）

当 pool_size 用完时，允许临时多创建的连接数。

```
pool_size(5) + max_overflow(7) = 12 连接上限

- 平时：5 个连接就够用
- 高峰期：5 个都在忙 → 临时再开最多 7 个
- 忙完后：溢出的 7 个会被关闭，只保留 5 个常驻
```

类比：忙的时候临时叫 7 个兼职，闲了就让他们回家。

---

### pool_pre_ping（连接前探活）

每次从池中取出连接时，先发 `SELECT 1` 检查连接是否活着。

```
request → 取出连接 → SELECT 1 → 正常？ → 执行真正的 SQL
                          ↓
                     连接已死 → 丢弃，重新创建连接
```

类比：服务员上菜前先看看盘子干不干净，脏了就换一个。

---

### pool_recycle（连接回收时间）

连接存活超过指定秒数后，主动关闭并重建。

```
连接创建时间线：
0s ──────── 300s ──────── 600s
│           │              │
创建        回收重建       再次回收
```

为什么需要？
- PostgreSQL 会杀掉空闲太久的连接
- 防止客户端拿着已被服务端关闭的连接去查询
- `pool_pre_ping` 是被动检测，`pool_recycle` 是主动预防

类比：规定服务员每 5 小时换班，避免疲劳出错。

---

## 5. 最终配置

### start.sh

```bash
# Gunicorn workers = 2 * CPU 核数（验证码已迁移到 Redis，可安全多 worker）
WORKERS=$(( $(nproc) * 2 ))

# 启动 Gunicorn 应用服务器
exec gunicorn app.main:app -w $WORKERS -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

### db.py

```python
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    pool_size=5,       # 常驻连接数
    max_overflow=7,    # 临时连接数
    pool_pre_ping=True,
    pool_recycle=300,
)
```

### 连接数计算（4 核机器）

```
Workers: 4 × 2 = 8
每 worker: 5 + 7 = 12
总计: 8 × 12 = 96 < PG max_connections(200)
余量: 104（留给管理工具、监控等）
```

---

## 6. 经验总结

1. **多 worker 不等于高性能** — 必须考虑数据库连接池、Redis 连接数等共享资源
2. **连接池配置要算总账** — `workers × (pool_size + max_overflow) < PG max_connections`
3. **从源头控制优先** — 减小连接池比增大 PG 连接数更优雅
4. **留足余量** — 管理工具、监控、备份都需要数据库连接

---

## 7. 关联文件

- `backend/start.sh` — Gunicorn 启动配置
- `backend/app/core/db.py` — 数据库连接池配置
- `docs/benchmark/2026-07-12_qps_benchmark.md` — QPS 测试报告
