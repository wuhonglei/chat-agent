# Chat Agent 面试知识图谱

> 项目：wuhonglei/chat-agent · FastAPI + React/Vite+ · PG + pgvector + Redis + Langfuse

## 架构图索引

| 文件 | 知识点 | 面试高频问题 |
|------|--------|-------------|
| [chat-agent-rag-architecture.html](html/chat-agent-rag-architecture.html) | 附件上传后的 RAG 检索全流程 | "你们项目 RAG 怎么做的？" "为什么用惰性索引？" "短文档和长文档怎么区分？" |
| [chat-agent-redis-architecture.html](html/chat-agent-redis-architecture.html) | Redis 在项目中的 4 大应用场景 | "Redis 在你项目里怎么用的？" "为什么缓存后来又去掉了？" "SSE 断连怎么补偿？" |
| [chat-agent-turn-idempotency.html](html/chat-agent-turn-idempotency.html) | Turn 幂等机制（SET NX 分布式锁） | "怎么防止重复创建消息？" "什么是幂等？" "为什么不用内存锁？" |

---

## 知识点详解

### 1. RAG 架构（附件上传 → 检索注入）

**核心流程**：上传写入路径 + 查询检索路径

- **上传时**：文件类型分发 → MinerU 转 Markdown → 磁盘落盘（不做 Embedding）
- **查询时**：读取附件文本 → Token 判断 → 短文档全文注入 / 长文档向量检索
- **向量检索**：MarkdownTextSplitter 分块 → bge-m3 Embedding → pgvector 余弦相似度（top_k=6）

**关键设计决策**：
- 惰性索引：上传时不做 Embedding，首次查询时才触发（Agent 模式用 grep 不用 Embedding；阈值可变无需迁移）
- content_id = SHA-256：天然去重，相同文件重复上传跳过
- 双策略分流：≤ 10K tokens 全文注入 / > 10K tokens 向量检索

**涉及代码**：
- `app/services/chat/kb_rag_context_service.py` — RAG 上下文构建
- `app/services/chat_upload/kb_chunk_embedding.py` — 分块向量索引
- `app/services/chat_upload/pdf.py` — PDF 上传处理
- `app/utils/multimodal.py` — 附件类型识别与遍历

---

### 2. Redis 应用架构（4 大场景）

**场景 ① SSE Stream Relay（核心价值）**
- Redis Stream (XADD/XREAD) 解耦 Producer/Consumer
- 每个 event 带自增 id，断连后 xrange 补漏 + xread 等新事件
- Lua 脚本原子操作：append 检查状态 / stop CAS 竞争
- close 后 TTL 缩短至 30min，支持窗口内续传

**场景 ② Turn 幂等**
- SET NX "pending" 抢锁 → 创建消息 → 写回 result
- 失败者 GET 轮询等待 result，超时 5s 返回 503
- 解决多 Worker 下网络重试导致的重复创建问题

**场景 ③ SMS 验证码**
- SET / GET / DELETE，TTL=300s（5 分钟过期）

**场景 ④ L2 用户缓存**
- Cache-Aside 模式，唯一存活的业务缓存
- 会话列表/详情/消息列表缓存已移除（数据体积极小 + 高频写 + PG 查询 0.07ms）

**涉及代码**：
- `app/services/chat/stream_relay.py` — SSE Stream Relay
- `app/services/chat/turn_idempotency_store.py` — Turn 幂等
- `app/services/auth/sms_verification_store.py` — SMS 验证码
- `app/core/cache.py` — L2 缓存（大部分已 no-op）
- `app/core/redis.py` — Redis 连接池配置

---

### 3. Turn 幂等机制

**问题**：网络重试 / 用户双击导致同一请求发送两次 → 重复创建消息

**方案**：Redis SET NX 分布式锁

```
SET NX key = "pending" (TTL=60s)
  ├─ 成功 → 创建消息 → SET key = {msg_ids} (TTL=7200s)
  └─ 失败 → GET 轮询等待 → 拿到 result → 复用
```

**为什么不用内存锁**：多 Worker 是独立进程，内存不共享。Redis 是共享状态层。

**防死锁**：pending TTL=60s 自动过期；create_fn 异常时主动 DELETE 释放锁

**涉及代码**：
- `app/services/chat/turn_idempotency_store.py` — 幂等存储
- `app/api/chat.py` — `/chat/stream` 接口中调用 `resolve_turn()`

---

## 面试高频问题速查

| 问题 | 回答要点 | 对应图 |
|------|---------|--------|
| RAG 怎么做的？ | 上传时只做文件转换，查询时才决定全文注入还是向量检索 | RAG 架构图 |
| 为什么惰性索引？ | Agent 模式用 grep 不需要 Embedding；阈值可变无需迁移 | RAG 架构图 |
| Redis 怎么用的？ | SSE 流式暂存（核心）+ Turn 幂等 + SMS 验证码 + 用户缓存 | Redis 架构图 |
| SSE 断连怎么补偿？ | Redis Stream 暂存事件 + 每个 event 带自增 id + xrange 补漏 | Redis 架构图 |
| 为什么缓存去掉了？ | 数据体积极小(P50=7KB) + PG 查询 0.07ms + 高频写命中率低 | Redis 架构图 |
| 什么是幂等？ | 一次操作和多次操作结果相同 | Turn 幂等图 |
| 怎么防止重复建消息？ | Redis SET NX 分布式锁，成功者建消息，失败者轮询等待复用 | Turn 幂等图 |
| 为什么不用内存锁？ | 多 Worker 独立进程，内存不共享 | Turn 幂等图 |
