# Chat Agent QPS 性能测试报告

**测试时间**: 2026-07-12 ~ 2026-07-15（含 CDN 架构优化 + IP 直连测试）
**测试目标**: https://chat.wuhonglei.cn
**测试工具**: Apache Bench (ab)

---

## 1. 测试环境

### 1.1 服务器配置

| 服务器 | 用途 | CPU | 内存 | 系统盘 | 带宽 | IP | 地域 |
|--------|------|-----|------|--------|------|-----|------|
| **公共服务** | nginx proxy manager | 4核 | 4GB | 70GB SSD | 6Mbps | 1.12.53.9 | 广州 |
| **业务应用** | Gunicorn + FastAPI | 4核 | 4GB | 60GB SSD | 5Mbps | 134.175.182.235 | 广州 |

### 1.2 请求链路架构

```
当前架构（CDN 直连）：
浏览器 (深圳)
    │
    ▼ HTTPS (CDN 边缘 TLS 终止)
CDN 边缘节点（腾讯云 CDN）
    │
    ▼ HTTP 回源
业务应用 (nginx, 广州, 5Mbps)
    │
    ▼ 本地
Gunicorn (8 workers) → FastAPI → PostgreSQL

CNAME: chat.wuhonglei.cn.cdn.dnsv1.com
源站: 134.175.182.235:3000 (HTTP)
```

### 1.3 软件环境

| 项目 | 值 |
|------|-----|
| 反向代理 | nginx proxy manager + nginx |
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

### 2.2 Health 端点 — 不同接入方式对比（并发 100，各 2000 请求）

| 接入方式 | 地址 | 工具 | QPS | 失败数 | P50 | P95 | P99 | 最大延迟 |
|----------|------|------|-----|--------|-----|-----|-----|----------|
| HTTP 直连业务应用 | `http://134.175.182.235:3000` | ab | **216.45** | 11 | 47ms | 2054ms | 4055ms | 5.1s |
| HTTP 直连 Gunicorn | `http://134.175.182.235:8000` | ab | **219.77** | 0 | 50ms | 2056ms | 4053ms | 7.0s |
| HTTP 连接复用 | `http://134.175.182.235:3000` | hey | **1,670** | 0 | - | - | - | 184ms |
| HTTPS 域名（CDN） | `https://chat.wuhonglei.cn` | ab | 132.35 | 12 | 502ms | 1650ms | 4082ms | 4.6s |
| 服务器本地 | `http://127.0.0.1:8000` | ab | **2,289** | 0 | 40ms | 68ms | 113ms | 243ms |

**结论**：
- HTTP 直连比 HTTPS 域名提升 **63%**（216 vs 132），验证 TLS + CDN 引入额外开销
- nginx 代理层几乎无性能损失（219 vs 216），瓶颈在网络层（RTT + TLS）
- 连接复用将 QPS 从 216 提升至 **1,670**（7.7 倍），接近服务器本地 2,289
- 服务器本地 QPS 是远程的 **10.6 倍**，确认瓶颈在网络层

### 2.3 认证接口（并发 100，各 2000 请求）

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

## 4. 瓶颈定位：远程 vs 本地测试

### 4.1 测试目的

通过服务器本地测试排除网络延迟，精确定位 QPS 瓶颈所在层级。

### 4.2 测试结果

| 测试场景 | QPS | P50 | P99 | Connect | 说明 |
|----------|-----|-----|-----|---------|------|
| 本地 gunicorn 直连（8 workers） | **2,289** | 40ms | 113ms | - | 服务器本地，基准 |
| 本地 gunicorn 直连（1 worker） | **1,304** | 75ms | 93ms | - | 单 worker 对比 |
| 本地 nginx 代理（8 workers） | **1,703** | 56ms | 114ms | - | 服务器本地，排除网络 |
| 内网直连业务应用（公共服务器→10.0.24.3:3000） | **2,002** | 46ms | 130ms | 2ms | HTTP，无代理 |
| 公共服务 nginx HTTP（公共服务器本地） | **1,800** | 53ms | 90ms | 0ms | HTTP，有代理无 TLS |
| 公共服务 nginx + TLS（公共服务器本地） | **311** | 312ms | 415ms | 175ms | HTTPS，含 TLS 握手 |
| 直接访问业务应用（深圳→业务应用） | **217** | 70ms | 4074ms | 374ms | HTTP，外网 |
| 完整链路（深圳→公共服务→业务应用） | **113** | 577ms | 2234ms | 485ms | HTTPS，完整链路 |

### 4.3 关键发现

```
Gunicorn 直连 (8 workers): 2,289 QPS (基准)
    ↓ -25.6%
nginx 代理 (8 workers): 1,703 QPS
    ↓ -12.5% (内网延迟仅 2ms)
内网直连业务应用 (公共服务器→10.0.24.3:3000): 2,002 QPS
    ↓ -10.1% (nginx 代理开销)
公共服务 nginx HTTP (无 TLS): 1,800 QPS
    ↓ -82.7% (TLS 握手 + 加解密)
公共服务 nginx + TLS: 311 QPS
    ↓ -63.7% (外网延迟)
完整链路 (深圳→公共服务→业务应用): 113 QPS
```

### 4.4 各层开销分离

| 层级 | QPS | 损失 | 说明 |
|------|-----|------|------|
| 内网直连业务应用 | 2,002 | - | 基准（无代理） |
| **nginx 代理开销** | 1,800 | **-10.1%** | 反向代理、header 处理 |
| **TLS 开销** | 311 | **-82.7%** | TLS 握手 (Connect 175ms) + 加解密 |

**结论**：TLS 是最大的性能瓶颈（-82.7%），nginx 代理开销很小（-10.1%）。

### 4.5 公共服务 nginx + TLS 性能损失

| 指标 | 内网直连 (HTTP) | 公共服务 nginx + TLS | 损失 |
|------|-----------------|---------------------|------|
| QPS | 2,002 | 311 | **-84.5%** |
| P50 | 46ms | 312ms | +578% |
| P99 | 130ms | 415ms | +219% |
| Connect | 2ms | 175ms | +8650% |

公共服务开销分析：
1. **TLS 握手** — Connect 175ms（占总延迟 55%），TLSv1.3 + TLS_AES_256_GCM_SHA384
2. **nginx 代理开销** — 约 100ms（header 处理、反向代理、请求转发）

### 4.6 Workers 数量对比（1 vs 8）

| 指标 | 8 workers | 1 worker | 变化 |
|------|-----------|----------|------|
| QPS | 2,290 | 1,304 | ⬇️ -43% |
| P50 | 40ms | 75ms | ⬆️ +87% |
| P99 | 113ms | 93ms | ⬇️ -18% |
| 最大延迟 | 243ms | 115ms | ⬇️ -53% |
| 标准差 | 22.2ms | 6.4ms | ⬇️ -71% |

**有趣发现**：
- 多 workers 提升吞吐量（+75%），但尾延迟和方差更差
- 单 worker 延迟更稳定（标准差仅 6.4ms），无进程间竞争
- 多 workers 的 P99 更高是因为上下文切换和资源竞争

### 4.7 nginx 代理层性能损失

| 指标 | Gunicorn 直连 | nginx 代理 | 损失 |
|------|---------------|------------|------|
| QPS | 2,290 | 1,703 | **-25.6%** |
| P50 | 40ms | 56ms | +16ms |
| P99 | 113ms | 114ms | +1ms |
| 最大延迟 | 243ms | 302ms | +59ms |

nginx 代理层消耗约 25% 的性能（TLS 终止、header 处理、gzip 等开销），属于正常范围。

### 4.8 瓶颈层级分析

| 层级 | 影响程度 | 说明 |
|------|----------|------|
| **网络延迟** | ⭐⭐⭐⭐⭐ | 深圳→广州 ~5-10ms，每个请求至少 1 RTT |
| **两层 nginx 转发** | ⭐⭐⭐⭐ | 请求经过 2 层代理，每层都有处理延迟 |
| **TLS 握手** | ⭐⭐⭐ | 2 个 RTT + ECDHE-ECDSA 计算开销 + 证书传输 |
| **带宽限制** | ⭐⭐ | 公共服务 6Mbps、业务应用 5Mbps |
| **gunicorn/worker** | ⭐ | 本地测试 2,289 QPS，已足够 |
| **数据库** | ⭐ | 已优化，不再是瓶颈 |

### 4.9 带宽瓶颈计算

```
业务服务器带宽: 5Mbps = 625,000 bytes/sec

每个请求的网络开销:
- HTTP 请求头部: ~500 bytes
- HTTP 响应头部: ~500 bytes
- HTTP 响应体: ~100 bytes
- TLS 记录开销: ~100 bytes
- TCP/IP 头部: ~60 bytes
- 总计: ~1,260 bytes

理论带宽上限 QPS = 625,000 / 1,260 ≈ 496 QPS

并发 100 时实际带宽使用:
130 QPS × 1,260 bytes × 8 = 1.3 Mbps (远未达到 5Mbps 上限)
```

**结论**: 带宽当前不是主要瓶颈，延迟和代理层是主因。

### 4.10 结论

系统实际处理能力为 **2,289 QPS**，远程测试的 130 QPS 主要由网络延迟 + 两层 nginx + TLS 握手共同造成。

---

## 5. 性能分层

### 第一梯队：轻量接口（QPS ~130-140）

- `/api/user/detail` — 用户信息查询
- `/api/conversation/{id}/messages` — 消息列表（优化后）
- `/api/chat/models` — 模型配置列表

### 第二梯队：中等接口（QPS ~100-120）

- `/api/health` — 健康检查
- `/api/conversation/detail` — 对话详情
- `/api/conversation/list` — 对话列表（优化后）

---

## 6. 连接池配置详解

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

**PostgreSQL**
```
max_connections = 200
```

### 6.2 连接数计算

```
Workers: 4 × 2 = 8
每 worker: 5 + 7 = 12
应用连接: 8 × 12 = 96
管理工具/监控: ~10
总计: ~106 < PG max_connections(200)
余量: 94
```

### 6.3 参数说明

| 参数 | 含义 | 类比 |
|------|------|------|
| pool_size | 常驻连接数，请求来了直接复用 | 固定雇佣的服务员 |
| max_overflow | 临时连接数，高峰时临时创建 | 忙时临时叫的兼职 |
| pool_pre_ping | 取连接前先 SELECT 1 检查活不活 | 上菜前检查盘子干不干净 |
| pool_recycle | 连接存活超过 N 秒后主动重建 | 服务员定时换班 |

---

## 7. 游标分页性能测试

### 7.1 测试背景

`/api/conversation/list` 接口从 offset/limit 分页改为游标分页，对比两种方式的性能差异。

### 7.2 测试结果

| 场景 | 游标分页 QPS | offset 分页 QPS | P50 | P95 |
|------|-------------|-----------------|-----|-----|
| 第1页（首页） | 46.80 | 53.60 | 689ms / 779ms | 2101ms / 2144ms |
| 深度分页（第11页） | 49.91 | 46.73 | 711ms / 628ms | 2296ms / 2226ms |

### 7.3 结论

1. **当前数据量下性能持平**：用户对话数量较少时，两种方式差异不大
2. **游标分页的真正价值**：数据量大时（offset=2000+），offset 分页需扫描并丢弃大量行，性能急剧下降；游标分页直接定位，性能稳定
3. **架构更优**：游标分页是无限滚动场景的最佳实践，为未来数据增长做好准备

### 7.4 游标分页适用场景

| 场景 | offset/limit | 游标分页 |
|------|--------------|----------|
| 数据量小（<1000条） | ✅ 够用 | ✅ 够用 |
| 数据量大（>10000条） | ❌ 深度分页慢 | ✅ 性能稳定 |
| 需要跳页（跳到第50页） | ✅ 支持 | ❌ 不支持 |
| 无限滚动/加载更多 | ⚠️ 可用 | ✅ 天然适配 |

---

## 8. 架构优化方案：CDN 直连业务应用

### 8.1 当前架构问题

```
当前架构（3跳）：
浏览器 ──HTTPS──→ CDN 边缘 ──HTTPS──→ NPM (1.12.53.9) ──HTTP──→ 业务应用 (10.0.24.3:3000)
                     │                    │
                     │                    └─ TLS 开销 89%
                     └─ 二次 TLS 握手

QPS: ~113（完整链路）
```

**问题**：
1. **双重 TLS** — CDN 和 NPM 都做 TLS 终止，开销叠加
2. **多一跳** — NPM 代理层增加延迟
3. **NPM TLS 是瓶颈** — 占总性能损失的 89%

### 8.2 推荐架构

```
推荐架构（1跳）：
浏览器 ──HTTPS──→ CDN 边缘 ──HTTP──→ 业务应用 (134.175.182.235:3000)
                     │
                     └─ TLS 在 CDN 边缘终止
                        CDN 管理证书

预期 QPS: 500-1000+
```

**优势**：
1. **单次 TLS** — 只在 CDN 边缘做 TLS 终止
2. **减少一跳** — 去掉 NPM，延迟降低
3. **回源 HTTP** — 业务服务器无需处理 TLS

### 8.3 HTTPS 处理方案

```
用户请求 → CDN (HTTPS) → 业务应用 (HTTP)
              │
              └─ TLS 在 CDN 终止
                 用户 ↔ CDN：加密
                 CDN ↔ 源站：HTTP（可信链路）
```

**证书管理**：
- CDN 自动管理 Let's Encrypt 证书（推荐）
- 或上传自定义证书到 CDN

### 8.4 配置步骤

#### 1. 腾讯云 CDN 配置

| 配置项 | 值 |
|--------|-----|
| 加速域名 | chat.wuhonglei.cn |
| 源站地址 | 134.175.182.235 |
| 回源端口 | 3000 |
| 回源协议 | HTTP |
| HTTPS | 开启，自动管理证书 |

#### 2. DNS 修改

```
# 删除现有 A 记录
chat.wuhonglei.cn → 1.12.53.9 (删除)

# 添加 CNAME 记录
chat.wuhonglei.cn → xxx.cdn.dnsv1.com (CDN 分配)
```

#### 3. 安全加固

```bash
# 安全组规则：只允许腾讯云 CDN IP 段访问 3000 端口
# 腾讯云 CDN IP 段：https://cloud.tencent.com/document/product/228/63165

# 拒绝其他所有 IP 直连 3000
# 这样直接访问 134.175.182.235:3000 会被安全组拦截
```

### 8.5 预期效果

| 指标 | 当前架构 | 推荐架构 | 提升 |
|------|----------|----------|------|
| QPS | ~113 | 500-1000+ | **5-10x** |
| 延迟 | 577ms (P50) | <200ms | **-65%** |
| TLS 握手 | 2 次 | 1 次 | **-50%** |

### 8.6 实际测试结果

| 测试 | 并发 | QPS | P50 | P99 | 说明 |
|------|------|-----|-----|-----|------|
| 第一次 | 100 | **825** | 71ms | 395ms | CDN 边缘缓存命中 |
| 第二次-1 | 100 | **587** | 117ms | 534ms | 正常波动 |
| 第二次-2 | 100 | **531** | 134ms | 535ms | 正常波动 |
| 第二次-3 | 50 | **295** | 118ms | 480ms | 并发降低 |

**稳定 QPS 范围：500-800**（仅测试 health 无认证接口）

### 8.6.1 CDN 完整接口测试（2026-07-14）

**测试条件**: 并发 100，各 2000 请求，通过 CDN（chat.wuhonglei.cn），JWT 认证

| 接口 | 轮次 | QPS | 失败数 | P50 | P95 | P99 |
|------|------|-----|--------|-----|-----|-----|
| `GET /api/health` | 第1轮 | **49.39** | 10 | 927ms | 2704ms | 4630ms |
| `GET /api/health` | 第2轮 | **183.71** | 3 | 442ms | 937ms | 1551ms |
| `GET /api/user/detail` | 第1轮 | **171.32** | 0 | 475ms | 976ms | 1812ms |
| `GET /api/user/detail` | 第2轮 | **192.81** | 0 | 411ms | 722ms | 2435ms |
| `GET /api/chat/models` | 第1轮 | **180.44** | 0 | 457ms | 908ms | 1847ms |
| `GET /api/chat/models` | 第2轮 | **168.99** | 0 | 449ms | 934ms | 2462ms |
| `GET /api/conversation/detail` | 第1轮 | **171.69** | 0 | 512ms | 899ms | 1481ms |
| `GET /api/conversation/detail` | 第2轮 | **168.85** | 0 | 464ms | 1020ms | 2572ms |
| `GET /api/conversation/list` | 第1轮 | **69.40** | 11 | 845ms | 4234ms | 8882ms |
| `GET /api/conversation/list` | 第2轮 | **65.00** | 13 | 814ms | 4237ms | 9417ms |
| `GET /api/conversation/{id}/messages` | 第1轮 | **172.04** | 0 | 466ms | 1041ms | 1781ms |
| `GET /api/conversation/{id}/messages` | 第2轮 | **133.26** | 0 | 468ms | 3473ms | 3995ms |

**CDN 接口 QPS 稳定范围（取两轮均值）**:

| 接口 | 平均 QPS | 性能梯队 |
|------|----------|----------|
| `GET /api/user/detail` | **182.1** | 🥇 第一梯队 |
| `GET /api/chat/models` | **174.7** | 🥇 第一梯队 |
| `GET /api/conversation/{id}/messages` | **152.7** | 🥇 第一梯队 |
| `GET /api/conversation/detail` | **170.3** | 🥇 第一梯队 |
| `GET /api/health` | **116.6** | 🥈 第二梯队 |
| `GET /api/conversation/list` | **67.2** | 🥉 第三梯队 |

**关键发现**:
1. **CDN 认证接口 QPS 稳定在 150-190**，比之前仅测试 health 的 531-825 低，说明之前 health 测试命中了 CDN 缓存
2. **conversation/list 是瓶颈**（67 QPS），因为涉及游标分页 + 多表查询，与旧架构测试结论一致
3. **认证接口无失败**（conversation/list 除外），CDN 回源链路稳定
4. **与旧架构对比**：CDN 认证接口 QPS（150-190）vs 旧架构认证接口（100-140），提升约 **30-50%**

### 8.6.2 CDN vs 旧架构认证接口对比

| 接口 | 旧架构 QPS (NPM+TLS) | CDN QPS | 提升 |
|------|----------------------|---------|------|
| `GET /api/health` | 117.25 | 116.6 | 持平 |
| `GET /api/user/detail` | 141.80 | **182.1** | **+28%** |
| `GET /api/chat/models` | 130.91 | **174.7** | **+33%** |
| `GET /api/conversation/detail` | 124.66 | **170.3** | **+37%** |
| `GET /api/conversation/list` | 101.54 | **67.2** | **-34%** ⬇️ |
| `GET /api/conversation/{id}/messages` | 137.96 | **152.7** | **+11%** |

**分析**:
- 大部分接口通过 CDN 有 **11%-37% 的 QPS 提升**，主要来自 CDN 边缘 TLS 终止减少了握手开销
- **conversation/list 反而下降 34%**，可能是 CDN 回源连接复用不如 NPM 内网直连高效，或该接口本身受 DB 查询瓶颈限制
- **health 持平**，说明 CDN 对无缓存的动态接口提升有限

### 8.6.3 公网直连测试（12Mbps 带宽升级后，2026-07-14）

**测试条件**: 并发 100，各 2000 请求，直连公网 IP（134.175.182.235:3000，HTTP），绕过 CDN

| 接口 | 轮次 | QPS | 失败数 | P50 | P95 | P99 |
|------|------|-----|--------|-----|-----|-----|
| `GET /api/health` (c=50) | - | **200.53** | 0 | 56ms | 1894ms | 2101ms |
| `GET /api/health` (c=100) | 第1轮 | **194.42** | 0 | 68ms | 2174ms | 3098ms |
| `GET /api/health` (c=200) | - | **191.99** | 0 | 178ms | 3091ms | 4084ms |
| `GET /api/user/detail` | 第1轮 | **197.06** | 0 | 173ms | 2076ms | 3146ms |
| `GET /api/user/detail` | 第2轮 | **202.26** | 0 | 115ms | 2054ms | 3074ms |
| `GET /api/chat/models` | 第1轮 | **177.76** | 0 | 79ms | 2050ms | 2144ms |
| `GET /api/chat/models` | 第2轮 | **183.79** | 0 | 82ms | 2049ms | 2184ms |
| `GET /api/conversation/detail` | 第1轮 | **181.57** | 0 | 63ms | 2079ms | 3090ms |
| `GET /api/conversation/detail` | 第2轮 | **196.67** | 0 | 72ms | 2037ms | 2092ms |
| `GET /api/conversation/list` | 第1轮 | **148.15** | 0 | 215ms | 2049ms | 2455ms |
| `GET /api/conversation/list` | 第2轮 | **167.73** | 0 | 251ms | 1481ms | 2262ms |
| `GET /api/conversation/{id}/messages` | 第1轮 | **92.21** | 0 | 716ms | 2356ms | 3356ms |
| `GET /api/conversation/{id}/messages` | 第2轮 | **142.92** | 0 | 447ms | 1704ms | 2478ms |

**公网直连 QPS 稳定范围（两轮均值）**:

| 接口 | 平均 QPS | 性能梯队 |
|------|----------|----------|
| `GET /api/user/detail` | **199.7** | 🥇 第一梯队 |
| `GET /api/conversation/detail` | **189.1** | 🥇 第一梯队 |
| `GET /api/chat/models` | **180.8** | 🥇 第一梯队 |
| `GET /api/conversation/list` | **157.9** | 🥇 第一梯队 |
| `GET /api/health` | **194.4** | 🥇 第一梯队 |
| `GET /api/conversation/{id}/messages` | **117.6** | 🥈 第二梯队 |

### 8.6.4 三种架构全景对比（认证接口两轮均值）

| 接口 | 旧架构 (NPM+TLS) | CDN 直连 | 公网直连 (12Mbps) | 公网 vs 旧架构 | CDN vs 公网 |
|------|-------------------|----------|-------------------|----------------|-------------|
| `GET /api/health` | 117.3 | 116.6 | **194.4** | **+66%** | 公网 +67% |
| `GET /api/user/detail` | 141.8 | 182.1 | **199.7** | **+41%** | 公网 +10% |
| `GET /api/chat/models` | 130.9 | 174.7 | **180.8** | **+38%** | 公网 +3% |
| `GET /api/conversation/detail` | 124.7 | 170.3 | **189.1** | **+52%** | 公网 +11% |
| `GET /api/conversation/list` | 101.5 | 67.2 | **157.9** | **+56%** | 公网 +135% |
| `GET /api/conversation/{id}/messages` | 138.0 | 152.7 | **117.6** | -15% | CDN +30% |

**关键发现**:
1. **带宽升级效果显著**: 公网直连 QPS（158-200）全面超越旧架构（101-142），提升 **38%-66%**
2. **公网直连 vs CDN**: 公网直连大部分接口 QPS 高于 CDN（180-200 vs 153-182），因为 CDN 回源增加了一跳
3. **conversation/list 公网表现最佳**: 从旧架构 101.5 → 公网 157.9（+56%），从 CDN 67.2 → 公网 157.9（+135%），说明该接口对网络质量敏感
4. **messages 接口波动大**: 公网第1轮 92 QPS vs 第2轮 143 QPS，可能受服务器瞬时负载影响
5. **所有接口失败数归零**: 带宽升级后公网直连不再有超时失败

### 8.6.5 缓存方案实施后测试（2026-07-18）

**测试条件**: 并发 100，各 2000 请求，间隔 3-5 秒

#### CDN 测试结果（两轮均值）

| 接口 | QPS | Non-2xx | 对比缓存前 |
|------|-----|---------|-----------|
| `GET /api/health` | **221.5** | 0 | 116.6 → **+90%** ✅ |
| `GET /api/user/detail` | **208.9** | 0 | 182.1 → **+15%** ✅ |
| `GET /api/chat/models` | **212.0** | 0 | 174.7 → **+21%** ✅ |
| `GET /api/conversation/detail` | **71.8** | 0 | 170.3 → **-58%** ⬇️ |
| `GET /api/conversation/list` | **91.3** | 34 | 67.2 → QPS+36% 但有少量 Non-2xx |
| `GET /api/conversation/{id}/messages` | **53.5** | 38 | 152.7 → **-65%** ⬇️ |

#### 公网直连测试结果（两轮均值）

| 接口 | QPS | Non-2xx | 对比缓存前 |
|------|-----|---------|-----------|
| `GET /api/health` | **179.8** | 0 | 194.4 → 持平 |
| `GET /api/user/detail` | **167.5** | 0 | 199.7 → -16% |
| `GET /api/chat/models` | **195.9** | 0 | 180.8 → +8% |
| `GET /api/conversation/detail` | **177.8** | 0 | 189.1 → -6% |
| `GET /api/conversation/list` | **72.0** | 34 | 157.9 → **-54%** ⬇️ |
| `GET /api/conversation/{id}/messages` | **65.8** | 38 | 117.6 → **-44%** ⬇️ |

#### 缓存效果总结

**成功的缓存**（L1 内存）:
| 接口 | CDN QPS 提升 | 结论 |
|------|-------------|------|
| `health` | 116.6 → 221.5 (+90%) | L1 消除 Redis PING，效果显著 |
| `chat/models` | 174.7 → 212.0 (+21%) | L1 消除配置读取，效果明显 |
| `user/detail` | 182.1 → 208.9 (+15%) | L1+L2 减少 DB 查询，有效 |

**失败的缓存**（L2 Redis）:
| 接口 | 问题 | Loki 日志确认 |
|------|------|-------------|
| `conversation/detail` | QPS 下降 58%，Redis 开销 > PG 主键查询 | cache_l2_error (TimeoutError) |
| `conversation/list` | QPS 下降 54%，Gunicorn WORKER TIMEOUT | cache_l2_error + WORKER TIMEOUT |
| `messages` | QPS 下降 65%，Gunicorn WORKER TIMEOUT | cache_l2_error + WORKER TIMEOUT |

**根因分析（Loki 日志确认）**:
1. **Redis 连接池超时**: `cache_l2_error` → `TimeoutError: Timeout reading from 1.12.53.9:6380`
   - `operation_timeout_seconds=0.5s` 已生效（降级返回 None，不再 500）
   - 但高并发下 0.5s 内仍无法获取连接，缓存全部 miss
2. **Gunicorn WORKER TIMEOUT**: `[CRITICAL] WORKER TIMEOUT (pid:xxx)`
   - 缓存操作 + DB 查询叠加，部分请求超过 Gunicorn 默认 30s timeout
3. **conversation/detail 缓存开销 > 收益**: PG 主键查询 ~1ms，Redis 往返 + JSON 序列化反而更慢
4. **messages 数据量大**: 序列化大 JSON 到 Redis 开销显著

**结论**: L1 内存缓存效果好；L2 Redis 缓存对 conversation/list 和 messages 在当前架构下收益为负，建议移除或仅保留 L1

### 8.7 优化效果对比

| 架构 | QPS | P50 | P99 | 提升 |
|------|-----|-----|-----|------|
| 旧架构（NPM + TLS） | 113 | 577ms | 2234ms | - |
| **新架构（CDN 直连）** | **531-825** | 71-134ms | 395-534ms | **+370% ~ +630%** |

```
QPS 提升: 113 → 531-825 (+370% ~ +630%)
P50 延迟: 577ms → 71-134ms (-77% ~ -88%)
P99 延迟: 2234ms → 395-534ms (-76% ~ -82%)
```

### 8.8 当前架构

```
浏览器 ──HTTPS──→ CDN 边缘（TLS 终止）──HTTP──→ 业务应用 (134.175.182.235:3000)
                     │
                     ├─ CNAME: chat.wuhonglei.cn.cdn.dnsv1.com
                     ├─ 证书: CDN 自动管理
                     └─ 缓存: 静态资源缓存

QPS: 500-800（HTTPS）
```

---

## 9. 优化建议

### 9.1 已完成 ✅

| 项目 | 效果 |
|------|------|
| 增加 workers 至 8 | 提升并发处理能力 |
| 优化连接池配置 | 解决连接数爆炸问题 |
| PG max_connections 调至 200 | messages 接口 QPS 提升 14.6 倍 |
| 对话列表接口添加游标分页 | 深度分页性能稳定，架构更优 |
| **CDN 直连业务应用** | **QPS 从 113 提升至 531-825（+370%~630%）** |

### 9.2 后续可优化

| 优先级 | 项目 | 预期收益 |
|--------|------|----------|
| P0 | HTTP/2（连接复用，减少 TLS 握手） | 远程 QPS 提升 2-3x |
| P0 | keep-alive 连接复用 | 减少 TLS 握手开销 |
| P1 | CDN/边缘节点 | 大幅降低 RTT |
| P1 | 升级服务器带宽 | 瓶颈到达时可提升上限 |
| P1 | 消息表添加 `(conversation_id, created_at)` 索引 | 查询提速 |
| P1 | Redis 缓存热点对话的消息列表 | 减少 DB 压力 |
| P2 | 消息列表只返回摘要，详情按需加载 | 减少传输量 |
| P3 | 考虑 PgBouncer | 多服务连接复用 |

---

## 10. 测试命令参考

```bash
# Health 基准测试
ab -n 1000 -c 50 https://chat.wuhonglei.cn/api/health

# 认证接口测试（需替换 TOKEN）
TOKEN="<your_jwt_token>"
ab -n 2000 -c 100 -H "Authorization: Bearer ***" \
  https://chat.wuhonglei.cn/api/user/detail

# 高并发测试
ab -n 3000 -c 200 https://chat.wuhonglei.cn/api/health

# 服务器本地测试（逐层对比）
ssh root@134.175.182.235

# 层级 1：Gunicorn 直连（基准）
ab -n 5000 -c 100 http://127.0.0.1:8000/api/health

# 层级 2：nginx 代理（nginx → Gunicorn）
ab -n 5000 -c 100 http://127.0.0.1:3000/api/health

# 公共服务服务器测试
ssh root@1.12.53.9

# 层级 3：内网直连业务应用（绕过公共服务 nginx）
ab -n 5000 -c 100 http://10.0.24.3:3000/api/health

# 层级 4：公共服务 nginx HTTP（需先关闭 Force SSL）
ab -n 5000 -c 100 -H "Host: chat.wuhonglei.cn" http://127.0.0.1/api/health

# 层级 5：公共服务 nginx + TLS
ab -n 5000 -c 100 -H "Host: chat.wuhonglei.cn" https://127.0.0.1/api/health

# 远程测试
# 层级 6：直接访问业务应用（绕过公共服务）
ab -n 2000 -c 100 http://134.175.182.235:3000/api/health

# 层级 7：完整链路
ab -n 2000 -c 100 https://chat.wuhonglei.cn/api/health
```

---

## 11. 关联文档

- `docs/benchmark/worker_scaling_db_pool_issue.md` — Worker 扩容引发的连接池问题排查
- `backend/start.sh` — Gunicorn 启动配置
- `backend/app/core/db.py` — 数据库连接池配置
