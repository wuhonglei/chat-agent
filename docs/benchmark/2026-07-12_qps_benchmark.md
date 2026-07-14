# Chat Agent QPS 性能测试报告

**测试时间**: 2026-07-12 ~ 2026-07-14
**测试目标**: https://chat.wuhonglei.cn
**测试工具**: Apache Bench (ab)

---

## 1. 测试环境

### 1.1 服务器配置

| 项目 | 值 |
|------|-----|
| CPU | 4 核 |
| 内存 | 4GB |
| 系统盘 | SSD 云硬盘 60GB |

### 1.2 软件环境

| 项目 | 值 |
|------|-----|
| 反向代理 | openresty |
| TLS | TLSv1.2, ECDHE-ECDSA-CHACHA20-POLY1305 |
| Gunicorn Workers | 8 (nproc × 2) |
| PostgreSQL | max_connections = 200 |
| 测试机 | macOS (深圳) |
| 测试工具 | ab (Apache Bench 2.3) |

---

## 2. 测试结果汇总

### 2.1 Health 端点（无认证，基准测试）

| 并发数 | 总请求数 | QPS | 失败数 | P50 | P95 | P99 | 最大延迟 |
|--------|----------|-----|--------|-----|-----|-----|----------|
| 50 | 1000 | **137.84** | 0 | 281ms | 660ms | 971ms | 1.9s |
| 100 | 2000 | **132.35** | 12 | 502ms | 1650ms | 4082ms | 4.6s |
| 200 | 3000 | **136.23** | 194 | 801ms | 3190ms | 6376ms | 18.3s |

### 2.2 认证接口（并发 100，各 2000 请求）

**最终配置**: WORKERS=8, pool_size=5, max_overflow=7, PG max_connections=200

| 接口 | QPS | 失败数 | P50 | P95 | P99 | 最大延迟 |
|------|-----|--------|-----|-----|-----|----------|
| `GET /api/health` | **117.25** | 0 | 544ms | 2260ms | 3457ms | 5.0s |
| `GET /api/user/detail` | **141.80** | 0 | 482ms | 2064ms | 3184ms | 5.8s |
| `GET /api/chat/models` | **130.91** | 0 | 521ms | 1864ms | 2783ms | 4.6s |
| `GET /api/conversation/detail` | **124.66** | 0 | 511ms | 2567ms | 3582ms | 5.4s |
| `GET /api/conversation/list` | **101.54** | 0 | 775ms | 2665ms | 4637ms | 6.2s |
| `GET /api/conversation/{id}/messages` | **137.96** | 0 | 254ms | 626ms | 1498ms | 1.5s |

---

## 3. 优化过程对比

### 3.1 测试场景

| 场景 | Workers | pool_size | max_overflow | PG max_connections | 说明 |
|------|---------|-----------|--------------|--------------------|----|
| ① 基准 | 1 | 20 | 30 | 100 | 初始单 worker |
| ② 扩容失败 | 8 | 20 | 30 | 100 | 连接数爆炸 |
| ③ 连接池优化 | 8 | 5 | 7 | 100 | 连接数受限 |
| ④ PG 扩容 | 8 | 5 | 7 | **200** | 最终配置 |

### 3.2 QPS 对比

| 接口 | ① 基准 (W=1) | ② 扩容失败 | ③ 连接池优化 | ④ PG 扩容 |
|------|---------------|------------|--------------|-----------|
| health | **137.84** | 38.62 ⬇️ | 134.23 ✅ | 117.25 |
| user/detail | 139.91 | 46.50 ⬇️ | 127.66 ✅ | **141.80** ✅ |
| chat/models | 103.25 | 18.49 ⬇️ | 104.61 ✅ | **130.91** ✅ |
| conversation/detail | 131.71 | 42.71 ⬇️ | 127.80 ✅ | 124.66 ✅ |
| conversation/list | 54.32 | 42.80 ⬇️ | 51.02 ✅ | **101.54** ✅ |
| messages | 10.01 | - | 9.46 | **137.96** ✅✅✅ |

### 3.3 关键发现

1. **场景②失败**: 8 workers × 50 连接 = 400，远超 PG max_connections=100
2. **场景③受限**: 连接池缩小后（96 < 100），QPS 恢复，但余量仅 4 个连接
3. **场景④成功**: PG max_connections=200 后：
   - `messages` 接口从 9.46 → **137.96 QPS**，提升 **14.6 倍**
   - `conversation/list` 从 51.02 → **101.54 QPS**，提升 **99%**
   - 所有接口失败数归零

---

## 4. 性能分层

### 第一梯队：轻量接口（QPS ~130-140）

- `/api/user/detail` — 用户信息查询
- `/api/conversation/{id}/messages` — 消息列表（优化后）
- `/api/chat/models` — 模型配置列表

### 第二梯队：中等接口（QPS ~100-120）

- `/api/health` — 健康检查
- `/api/conversation/detail` — 对话详情
- `/api/conversation/list` — 对话列表（优化后）

---

## 5. 连接池配置详解

### 5.1 最终配置

**start.sh**
```bash
# Gunicorn workers = 2 * CPU 核数
WORKERS=$(( $(nproc) * 2 ))
exec gunicorn app.main:app -w $WORKERS -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

**db.py**
```python
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    pool_size=5,       # 常驻连接数
    max_overflow=7,    # 临时连接数
    pool_pre_ping=True,
    pool_recycle=300,
)
```

**PostgreSQL**
```
max_connections = 200
```

### 5.2 连接数计算

```
Workers: 4 × 2 = 8
每 worker: 5 + 7 = 12
应用连接: 8 × 12 = 96
管理工具/监控: ~10
总计: ~106 < PG max_connections(200)
余量: 94
```

### 5.3 参数说明

| 参数 | 含义 | 类比 |
|------|------|------|
| pool_size | 常驻连接数，请求来了直接复用 | 固定雇佣的服务员 |
| max_overflow | 临时连接数，高峰时临时创建 | 忙时临时叫的兼职 |
| pool_pre_ping | 取连接前先 SELECT 1 检查活不活 | 上菜前检查盘子干不干净 |
| pool_recycle | 连接存活超过 N 秒后主动重建 | 服务员定时换班 |

---

## 6. 游标分页性能测试

### 6.1 测试背景

`/api/conversation/list` 接口从 offset/limit 分页改为游标分页，对比两种方式的性能差异。

### 6.2 测试结果

| 场景 | 游标分页 QPS | offset 分页 QPS | P50 | P95 |
|------|-------------|-----------------|-----|-----|
| 第1页（首页） | 46.80 | 53.60 | 689ms / 779ms | 2101ms / 2144ms |
| 深度分页（第11页） | 49.91 | 46.73 | 711ms / 628ms | 2296ms / 2226ms |

### 6.3 结论

1. **当前数据量下性能持平**：用户对话数量较少时，两种方式差异不大
2. **游标分页的真正价值**：数据量大时（offset=2000+），offset 分页需扫描并丢弃大量行，性能急剧下降；游标分页直接定位，性能稳定
3. **架构更优**：游标分页是无限滚动场景的最佳实践，为未来数据增长做好准备

### 6.4 游标分页适用场景

| 场景 | offset/limit | 游标分页 |
|------|--------------|----------|
| 数据量小（<1000条） | ✅ 够用 | ✅ 够用 |
| 数据量大（>10000条） | ❌ 深度分页慢 | ✅ 性能稳定 |
| 需要跳页（跳到第50页） | ✅ 支持 | ❌ 不支持 |
| 无限滚动/加载更多 | ⚠️ 可用 | ✅ 天然适配 |

---

## 7. 优化建议

### 7.1 已完成 ✅

| 项目 | 效果 |
|------|------|
| 增加 workers 至 8 | 提升并发处理能力 |
| 优化连接池配置 | 解决连接数爆炸问题 |
| PG max_connections 调至 200 | messages 接口 QPS 提升 14.6 倍 |
| 对话列表接口添加游标分页 | 深度分页性能稳定，架构更优 |

### 7.2 后续可优化

| 优先级 | 项目 | 预期收益 |
|--------|------|----------|
| P1 | 消息表添加 `(conversation_id, created_at)` 索引 | 查询提速 |
| P1 | Redis 缓存热点对话的消息列表 | 减少 DB 压力 |
| P2 | 消息列表只返回摘要，详情按需加载 | 减少传输量 |
| P3 | 考虑 PgBouncer | 多服务连接复用 |

---

## 8. 测试命令参考

```bash
# Health 基准测试
ab -n 1000 -c 50 https://chat.wuhonglei.cn/api/health

# 认证接口测试（需替换 TOKEN）
TOKEN="<your_jwt_token>"
ab -n 2000 -c 100 -H "Authorization: Bearer $TOKEN" \
  https://chat.wuhonglei.cn/api/user/detail

# 高并发测试
ab -n 3000 -c 200 https://chat.wuhonglei.cn/api/health
```

---

## 9. 关联文档

- `docs/benchmark/worker_scaling_db_pool_issue.md` — Worker 扩容引发的连接池问题排查
- `backend/start.sh` — Gunicorn 启动配置
- `backend/app/core/db.py` — 数据库连接池配置
