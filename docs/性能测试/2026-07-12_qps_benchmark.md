# Chat Agent QPS 性能测试报告

**测试时间**: 2026-07-12
**测试目标**: https://chat.wuhonglei.cn
**测试工具**: Apache Bench (ab)

---

## 1. 测试环境

| 项目 | 值 |
|------|-----|
| 服务器 | openresty (反向代理) |
| TLS | TLSv1.2, ECDHE-ECDSA-CHACHA20-POLY1305 |
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

### 2.2 认证接口（并发 50，各 500 请求）

| 接口 | QPS | 失败数 | P50 | P95 | P99 | 最大延迟 |
|------|-----|--------|-----|-----|-----|----------|
| `GET /api/health` | **137.84** | 0 | 281ms | 660ms | 971ms | 1.9s |
| `GET /api/user/detail` | **139.91** | 0 | 257ms | 717ms | 997ms | 1.2s |
| `GET /api/chat/models` | **103.25** | 0 | 300ms | 1045ms | 1829ms | 2.6s |
| `GET /api/conversation/detail` | **131.71** | 0 | 322ms | 749ms | 1158ms | 2.1s |
| `GET /api/conversation/list` | **54.32** | 0 | 657ms | 2147ms | 3844ms | 5.2s |
| `GET /api/conversation/{id}/messages` | **10.01** | 0 | 3726ms | 10613ms | 18657ms | 31.3s |

---

## 3. 性能分层

### 第一梯队：轻量接口（QPS ~130-140）

- `/api/health` — 纯健康检查，无 DB 查询
- `/api/user/detail` — 用户信息查询，简单主键查询
- `/api/conversation/detail` — 单条对话详情，主键查询

**特点**: 接近系统上限，瓶颈在 openresty/uvicorn 层，非业务逻辑。

### 第二梯队：中等接口（QPS ~100）

- `/api/chat/models` — 模型配置列表，需读取配置

### 第三梯队：DB 查询接口（QPS ~50）

- `/api/conversation/list` — 对话列表，涉及分页查询 + 排序

### 第四梯队：重查询接口（QPS ~10）⚠️

- `/api/conversation/{id}/messages` — 消息列表，**性能瓶颈**

---

## 4. 瓶颈分析

### 4.1 系统级瓶颈

并发从 50 → 200，QPS 始终维持在 ~130-140，说明：
- 系统在 50 并发时已接近处理上限
- 可能受限于 Uvicorn worker 数量或 openresty 连接数

### 4.2 `/api/conversation/messages` 接口瓶颈

该接口 P50 延迟 3.7s，P99 延迟 18.6s，QPS 仅 10，远低于其他接口。

可能原因：
1. **消息表数据量大** — 该对话 (7abca92b) 可能包含大量消息
2. **缺少数据库索引** — conversation_id 外键未建索引
3. **N+1 查询** — 消息关联了附件、工具调用记录等，逐条查询
4. **返回数据过多** — 未分页，一次性加载全部消息

---

## 5. 优化建议

### 5.1 短期优化

| 项目 | 预期收益 |
|------|----------|
| 增加 Uvicorn workers (当前可能为 1) | QPS 翻倍 |
| 检查 openresty `worker_connections` 配置 | 提升并发上限 |
| `/api/conversation/messages` 添加分页 | QPS 提升 5-10x |
| 消息表添加 `(conversation_id, created_at)` 索引 | 查询提速 |

### 5.2 中期优化

| 项目 | 预期收益 |
|------|----------|
| Redis 缓存热点对话的消息列表 | 减少 DB 压力 |
| 对话列表接口添加游标分页（代替 offset） | 大 offset 下性能稳定 |
| 消息列表只返回摘要，详情按需加载 | 减少传输量 |

---

## 6. 测试命令参考

```bash
# Health 基准测试
ab -n 1000 -c 50 https://chat.wuhonglei.cn/api/health

# 认证接口测试（需替换 TOKEN）
TOKEN="<your_jwt_token>"
ab -n 500 -c 50 -H "Authorization: Bearer $TOKEN" \
  https://chat.wuhonglei.cn/api/user/detail

# 高并发测试
ab -n 2000 -c 100 https://chat.wuhonglei.cn/api/health
```

---

## 7. 后续测试计划

- [ ] SSE 流式接口 (`/api/chat`) QPS 测试（需 k6 或 locust）
- [ ] 不同 worker 数量下的对比测试
- [ ] `/api/conversation/messages` 接口 SQL 慢查询分析
- [ ] 生产环境 Redis 缓存命中率监控
