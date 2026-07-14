# Chat Agent QPS 性能测试报告

**测试时间**: 2026-07-12 ~ 2026-07-14
**测试目标**: https://chat.wuhonglei.cn
**测试工具**: Apache Bench (ab)
**服务器**: 4 核 CPU

---

## 1. 测试环境

| 项目 | 值 |
|------|-----|
| 服务器 | openresty (反向代理) |
| TLS | TLSv1.2, ECDHE-ECDSA-CHACHA20-POLY1305 |
| 测试机 | macOS (深圳) |
| 测试工具 | ab (Apache Bench 2.3) |
| CPU 核数 | 4 |

---

## 2. 测试结果汇总

### 2.1 Health 端点（无认证，基准测试）

| 并发数 | 总请求数 | QPS | 失败数 | P50 | P95 | P99 | 最大延迟 |
|--------|----------|-----|--------|-----|-----|-----|----------|
| 50 | 1000 | **137.84** | 0 | 281ms | 660ms | 971ms | 1.9s |
| 100 | 2000 | **132.35** | 12 | 502ms | 1650ms | 4082ms | 4.6s |
| 200 | 3000 | **136.23** | 194 | 801ms | 3190ms | 6376ms | 18.3s |

### 2.2 认证接口（并发 100，各 2000 请求，WORKERS=8，pool_size=5，max_overflow=7）

| 接口 | QPS | 失败数 | P50 | P95 | P99 | 最大延迟 |
|------|-----|--------|-----|-----|-----|----------|
| `GET /api/health` | **134.23** | 6 | 560ms | 1657ms | 2743ms | 4.6s |
| `GET /api/user/detail` | **127.66** | 0 | 540ms | 1727ms | 4167ms | 9.8s |
| `GET /api/chat/models` | **104.61** | 0 | 615ms | 2243ms | 5155ms | 15.1s |
| `GET /api/conversation/detail` | **127.80** | 0 | 556ms | 1608ms | 2750ms | 10.2s |
| `GET /api/conversation/list` | **51.02** | 1 | 1220ms | 4820ms | 8833ms | 30.2s |
| `GET /api/conversation/{id}/messages` | **9.46** | 0 | 3828ms | 10413ms | 21380ms | 38.5s |

---

## 3. Worker 扩容优化对比

### 3.1 测试场景

| 场景 | Workers | pool_size | max_overflow | 最大连接数 |
|------|---------|-----------|--------------|-----------|
| ① 基准 | 1 | 20 | 30 | 50 |
| ② 扩容（连接池未调） | 8 | 20 | 30 | 400 ⚠️ |
| ③ 扩容（连接池优化） | 8 | 5 | 7 | 96 |

### 3.2 QPS 对比

| 接口 | ① 基准 (W=1) | ② 扩容 (pool=20/30) | ③ 优化后 (pool=5/7) |
|------|---------------|---------------------|---------------------|
| health | **137.84** | 38.62 ⬇️ | **134.23** ✅ |
| user/detail | **139.91** | 46.50 ⬇️ | **127.66** ✅ |
| chat/models | 103.25 | 18.49 ⬇️ | **104.61** ✅ |
| conversation/detail | 131.71 | 42.71 ⬇️ | **127.80** ✅ |
| conversation/list | **54.32** | 42.80 ⬇️ | 51.02 ✅ |
| messages | 10.01 | - | 9.46 |

### 3.3 结论

- **场景②失败原因**: 8 workers × 50 连接 = 400，远超 PG 默认 max_connections=100，导致连接排队
- **场景③成功**: 连接池缩小后（96 < 100），QPS 恢复到单 worker 水平
- **最终结论**: ~130 QPS 是当前架构上限，多 worker 未带来提升

---

## 4. 性能分层

### 第一梯队：轻量接口（QPS ~130）

- `/api/health` — 纯健康检查，无 DB 查询
- `/api/user/detail` — 用户信息查询，简单主键查询
- `/api/conversation/detail` — 单条对话详情，主键查询

**特点**: 接近系统上限，瓶颈在 openresty/gunicorn 层。

### 第二梯队：中等接口（QPS ~100）

- `/api/chat/models` — 模型配置列表，需读取配置

### 第三梯队：DB 查询接口（QPS ~50）

- `/api/conversation/list` — 对话列表，涉及分页查询 + 排序

### 第四梯队：重查询接口（QPS ~10）⚠️

- `/api/conversation/{id}/messages` — 消息列表，**性能瓶颈**

---

## 5. 瓶颈分析

### 5.1 系统级瓶颈

- QPS 上限 ~130，在 50 并发时已达峰值
- 多 worker（8 workers）未提升 QPS，说明瓶颈在：
  - openresty 反向代理层
  - 网络延迟（深圳 → 服务器）
  - 或 gunicorn master 进程调度

### 5.2 `/api/conversation/messages` 接口瓶颈

该接口 P50 延迟 3.8s，P99 延迟 21.4s，QPS 仅 10，远低于其他接口。

可能原因：
1. **消息表数据量大** — 该对话 (7abca92b) 可能包含大量消息
2. **缺少数据库索引** — conversation_id 外键未建索引
3. **N+1 查询** — 消息关联了附件、工具调用记录等，逐条查询
4. **返回数据过多** — 未分页，一次性加载全部消息

---

## 6. 连接池配置优化

### 6.1 最终配置

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

### 6.2 连接数计算

```
Workers: 4 × 2 = 8
每 worker: 5 + 7 = 12
总计: 8 × 12 = 96 < PG max_connections(100)
```

### 6.3 参数说明

| 参数 | 含义 | 类比 |
|------|------|------|
| pool_size | 常驻连接数，请求来了直接复用 | 固定雇佣的服务员 |
| max_overflow | 临时连接数，高峰时临时创建 | 忙时临时叫的兼职 |
| pool_pre_ping | 取连接前先 SELECT 1 检查活不活 | 上菜前检查盘子干不干净 |
| pool_recycle | 连接存活超过 N 秒后主动重建 | 服务员定时换班 |

---

## 7. 优化建议

### 7.1 已完成 ✅

| 项目 | 效果 |
|------|------|
| 增加 workers 至 8 | QPS 未提升，但提升并发处理能力 |
| 优化连接池配置 | 解决连接数爆炸问题，QPS 恢复正常 |

### 7.2 待优化

| 优先级 | 项目 | 预期收益 |
|--------|------|----------|
| P0 | `/api/conversation/messages` 添加分页 | QPS 提升 5-10x |
| P0 | 消息表添加 `(conversation_id, created_at)` 索引 | 查询提速 |
| P1 | 调大 PG max_connections 至 200 | 留足余量（当前仅剩 4） |
| P1 | Redis 缓存热点对话的消息列表 | 减少 DB 压力 |
| P2 | 对话列表接口添加游标分页（代替 offset） | 大 offset 下性能稳定 |
| P2 | 消息列表只返回摘要，详情按需加载 | 减少传输量 |

### 7.3 Worker 调优建议

当前 4 核机器，`nproc * 2 = 8` workers 已足够。如果 QPS 仍是瓶颈：

1. **先优化慢接口**（messages），效果更明显
2. **考虑 PgBouncer**，如果未来需要更多 workers
3. **不建议继续增加 workers**，4 核机器 8 workers 已是上限

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
