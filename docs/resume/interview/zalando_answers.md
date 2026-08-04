# Zalando Agent 后端二面 — 完整回答（结合 Shopee AI 智能助手项目 + pydantic-ai）

---

## 一、框架深度题

### 1.1 Pydantic-AI 核心设计、与自研 ReAct 引擎差异

#### Q1: pydantic-ai 核心优势 + 对比 Shopee 自研 ReAct Loop

**pydantic-ai 三大核心优势：**

1. **类型安全的结构化输出** — `output_type` 传入 BaseModel，框架自动注入 tool schema 或 `response_format`，返回值有 IDE 自动补全 + Pydantic 校验
2. **依赖注入** — `RunContext[Deps]` 让工具/系统提示/输出校验器按类型拿上下文，无需手动传参
3. **内置重试** — 输出校验失败时自动把 `ValidationError` 作为 `RetryPromptPart` 回传模型修正，`retries` 可分层配置

**对比自研 ReAct Loop（项目核心）：**

| 维度 | pydantic-ai | Shopee 自研 |
|------|-------------|-------------|
| 工具循环 | 框架内部 while loop + tool_call 解析 | 自研 `ChatRoundStateMachine` 状态机驱动，`for iteration in range(MAX)` 逐轮编排 |
| 流式 | `agent.run_stream()` 原生支持 | 自建 SSE 生成器 + `ContentBlocksAggregator`，每轮 yield sse event |
| 输出校验 | BaseModel 自动 + `output_validator` 装饰器 | 自行写 JSON parse + schema 检查，失败手动重试 |
| 工具治理 | 无内置熔断/防死循环 | 自研 `ToolCallGuardrail` 三层防护（详见 Q6） |
| 上下文管理 | 基本靠 `message_history` 手动管理 | 自研四级 `unified_context_guard`（详见 Q4） |
| MCP 原生支持 | 2026 年新增 MCPToolset / MCP capability | 项目一开始就基于 MCP 协议自建工具生态 |

**核心判断：** pydantic-ai 适合快速搭建工具型 Agent，但对电商长会话场景缺三样东西：上下文分级压缩、工具调用防死循环、流式断连续传。项目选自研是因为这些是电商高频场景刚需。

---

#### Q2: RunContext 依赖注入 vs 自研 MCP 工具类型校验

**pydantic-ai 方式：**

```python
@dataclass
class Deps:
    user_id: str
    db: Database

@agent.tool
def get_order(ctx: RunContext[Deps], order_id: str) -> str:
    # ctx.deps.user_id 自动注入，order_id 由 LLM 填充
    return ctx.deps.db.query(order_id)
```

优势：工具参数类型由 Python type hint 自动推导，LLM 返回的 JSON 自动 Pydantic 校验。

**项目怎么做同等能力：**

1. **MCP 工具定义层** — 每个 MCP server 的 tool schema 本身就是 JSON Schema，参数类型约束写在 MCP server 注册时（如 price 必须 number、size 枚举 S/M/L/XL）
2. **ToolExecutor 执行前校验** — `mcp_tool_execution.py` 中 `execute_tool_calls_parallel` 在调 MCP server 前，由 MCP server 自身做参数校验（MCP 协议要求 server 返回错误）
3. **会话上下文注入** — user_id / conversation_id 通过 `MCPToolSession.reset_for_request()` 写入，ToolExecutor 执行时自动注入到 MCP 调用上下文

**取舍：** pydantic-ai 的优势是校验在 Python 层一步完成，开发体验好。项目把校验下沉到 MCP server 层，好处是工具定义和校验逻辑跟 Agent 代码解耦，多语言 MCP server 都能接，但调试链路长一层。

---

#### Q3: 结构化输出校验 + 失败重试 vs 项目方案

**pydantic-ai 机制：**

- `output_type=SomeModel` → 框架自动构造 `final_result` tool schema，模型返回 tool_call
- 如果模型返回的 JSON 不符合 schema → Pydantic `ValidationError` → 框架自动发 `RetryPromptPart`（含错误信息）给模型 → 重试 retries 次
- 默认 1 次重试，可配 `retries=3` 或 `retries={'output': 5, 'tools': 2}`

**项目如何解决：**

1. **非结构化输出** — 最终回答是自由文本，不走 JSON schema 校验，由模型直接生成
2. **工具参数错乱** — MCP server 端做参数校验，返回错误消息作为 tool_result，LLM 看到错误后自行修正下一轮调用（本质是 ReAct 自循环重试）
3. **模型返回非法 JSON 场景** — 主要出现在 tool_call 的 arguments 解析，项目中 `_truncate_tool_call_args_json` 对超长 args 做安全截断防止 JSON break；如果 LLM 返回不可解析的 tool_call，直接丢弃并注入提示让模型重新生成

**面试加分点：** pydantic-ai 的 `output_type` 重试是"封闭系统"内的修正（框架控制 LLM 对话历史），而项目的 ReAct 循环天然支持多轮修正，等价于 `retries=MAX_ITERATIONS`，但消耗更多 token。

---

#### Q4: mem0 跨会话记忆 + pydantic-ai 适配

**pydantic-ai 原生局限：** 框架只有 `message_history` 参数做会话内上下文传递，无跨会话持久记忆。

**项目 mem0 集成方案：**

1. `MemoryService` 调 mem0 REST API，按 user_id 维度存储/检索
2. 每次请求前：`chat_orchestrator` 调 `memory_service.get_memories(user_id)` → 注入 `user_memories`
3. 注入位置：`get_user_message_for_tool_calls()` 把 memories 编入 user message 的上下文区（与 kb_context、window_out_summary 并列）
4. 区分临时/长期：当前对话筛选条件在 `_working_history` 中（会话结束即丢），用户穿搭偏好通过 mem0 持久化（跨会话）

**适配 pydantic-ai 的方案：**

```python
@dataclass
class Deps:
    user_id: str
    memories: list[str]  # 前置从 mem0 检索

@agent.system_prompt
def memory_prompt(ctx: RunContext[Deps]) -> str:
    return "用户偏好: " + "\n".join(ctx.deps.memories)
```

本质就是把 mem0 检索逻辑放在 `Agent.run()` 的 deps 构造阶段，通过 RunContext 注入系统提示。和项目方案逻辑一致，只是注入方式从"拼 user message"变成"注入 system_prompt"。

---

#### Q5: 流式 SSE 对比

**pydantic-ai 流式：**

```python
async with agent.run_stream('prompt') as stream:
    async for text in stream.stream_text():
        yield text  # 逐 token 文本
# 结构化流式：
    async for partial in stream.stream_output():
        yield partial  # 逐字段 BaseModel 片段
```

优势：API 简洁，结构化输出也能流式。局限：框架内部管理 stream 生命周期，断连后无法从断点续传。

**项目方案（FastAPI StreamingResponse + Redis Stream）：**

1. FastAPI SSE 端点用 `AsyncGenerator[str, None]` 逐事件 yield
2. `ContentBlocksAggregator` 聚合 tool_call deltas → 完整 tool_call → 执行 → 流式返回 tool_result
3. Redis Stream 做消息持久化：每条 SSE event 写入 Redis Stream（message_id 递增），断连后客户端带 `last_message_id` 重连 → 从 Redis 读取断点后的消息续传

**对比：**

| 维度 | pydantic-ai | Shopee 方案 |
|------|-------------|-------------|
| 断连续传 | 不支持 | Redis Stream 消息 ID 续传 |
| 工具中间结果流式 | 不直接暴露 tool_result 流 | SSE 中 tool_call/tool_result 都是独立 event |
| 复杂度 | 低 | 高（需维护 Redis Stream + 客户端重连协议） |
| 适用场景 | 短交互 | 电商长会话高频断连 |

---

#### Q6: 工具调用熔断 + 防死循环

**pydantic-ai 原生能力：** 有 `retries` 参数但只针对输出校验失败，对工具调用死循环无内置防护。

**项目三层 Guardrail 机制（`tool_call_guardrail.py`）：**

**第一层：精确参数重复阻断**
- 对每次 tool_call 计算 `sha256(tool_name + sorted_args)` 签名
- 相同签名连续失败 ≥5 次 → BLOCK，返回"请更换参数或换用其他工具"
- 连续失败 ≥2 次先发 ⚠️ 警告

**第二层：同工具连续失败熔断**
- 按 tool_name 维度累计失败次数
- 同一工具连续失败 ≥8 次 → `halt=True`，全量熔断
- ≥3 次发警告 + recovery hint（shell 工具建议先 `pwd && ls -la`，文件工具建议检查路径）

**第三层：无进展检测**
- 对幂等工具（如搜索、查询），每次结果 hash 比对
- 相同参数相同结果连续 ≥5 次 → BLOCK
- ≥3 次发警告"可能没有进展"

**迁移到 pydantic-ai：**

```python
guardrail = ToolCallGuardrail()

@agent.tool
async def search_products(ctx: RunContext[Deps], query: str) -> str:
    decision = guardrail.before_call("search_products", {"query": query})
    if decision.kind == "halt":
        raise ModelRetry(decision.message)
    if decision.kind == "block":
        raise ModelRetry(decision.message)
    result = await do_search(query)
    guardrail.record_outcome(
        tool_name="search_products",
        arguments={"query": query},
        success=True, content=result,
    )
    return result
```

通过 `ModelRetry` 让模型自行修正策略，等价于项目的 warn → block → halt 渐进升级。

---

#### Q7: CI 无 LLM 密钥测试 Agent

**pydantic-ai 测试方案：**

- 内置 `TestModel` 和 `FunctionModel` 用于测试：

```python
from pydantic_ai.models.test import TestModel

test_model = TestModel(output=CityInfo(name='深圳', population=17680000))
agent = Agent(test_model, output_type=CityInfo)
result = agent.run_sync('test')  # 不调真实 LLM
```

- `TestModel` 自动按 output_type schema 生成数据，可测工具调用链路

**结合项目 Jest 质量门禁：**

1. **后端测试：** `make lint`（ruff）+ `make test`（pytest，`--ignore=tests/mcp_demo` 跳过需真实 API 的测试）
2. **MCP 工具测试：** mock MCP server 返回固定响应，不走真实 LLM
3. **Guardrail 测试：** `test_tool_guardrails.py` 直接构造 `ChatCompletionMessageFunctionToolCall` 对象，不经过 LLM
4. **前端：** `vp lint .`（oxlint）+ `vp build`（编译检查）

**面试关键点：** pydantic-ai 的 `TestModel` 降低了 Agent 测试门槛（无需 mock LLM 调用），但 Guardrail、上下文守卫等逻辑是纯 Python，pytest 直接测，不依赖 LLM mock。两者测试策略本质一致：把 LLM 调用隔离在测试边界之外。

---

### 1.2 MCP 协议深度

#### Q1: MCP 协议是什么？Shopee 标准化落地 + 与 pydantic-ai 原生工具取舍

**MCP (Model Context Protocol) 定义：**

Anthropic 提出的开放协议，标准化 LLM 与外部工具/数据源的通信。核心思想：工具提供方实现 MCP Server（暴露 tool schema + 执行逻辑），消费方用 MCP Client 连接，协议层统一 JSON-RPC 2.0 消息格式、工具发现、参数校验。

**项目 MCP 落地方式：**

1. `MCPClientManager` 管理多个 MCP Server 连接（stdio 本地进程 / SSE 远程），连接池 `MCPConnectionPool` 统一生命周期
2. 每个 MCP Server 注册时声明 tools（name + description + JSON Schema parameters）
3. Agent 请求时：`mcp_manager.get_tools_for_llm(server_names)` → 拿到所有工具 schema → 注入 LLM 的 tools 参数
4. LLM 返回 tool_call → `MCPToolSession` 路由到对应 MCP Server 执行 → 结果作为 tool_result 回传

**与 pydantic-ai 原生工具调用取舍：**

| 维度 | MCP 工具（项目） | pydantic-ai `@agent.tool` |
|------|-----------------|--------------------------|
| 工具定义 | MCP Server 独立进程，JSON Schema 声明 | Python 函数 + type hint，框架自动生成 schema |
| 跨语言 | 支持（任何语言实现 MCP Server） | 仅 Python |
| 工具热更新 | 支持（重启 MCP Server 不影响 Agent） | 需重新部署 Agent |
| 多 Agent 共享 | 支持（多个 Agent 连同一 MCP Server） | 工具绑定在 Agent 实例上 |
| 调试链路 | 长（Agent → MCP Client → MCP Server → 实际 API） | 短（直接函数调用） |
| 类型校验 | MCP Server 端做 | Pydantic 自动做 |
| 延迟 | 多一层 IPC/SSE 传输开销 | 进程内调用，几乎无开销 |

**面试结论：** MCP 适合"工具生态需要独立演进、多团队协作、多 Agent 共享"的场景（Zalando 多团队各维护自己的 MCP Server）。pydantic-ai `@agent.tool` 适合"工具逻辑简单、单 Agent 独占"的场景。最佳实践是混合使用——核心高频工具用 `@agent.tool` 减少延迟，外部团队维护的工具走 MCP。

---

#### Q2: 多工具权限隔离、参数校验、超时控制

**电商场景：** 商品搜索、库存查询、比价、用户画像读取，四个 MCP Server 由不同团队维护，权限和安全等级不同。

**权限隔离：**

1. **MCP Server 声明级** — 每个 Server 在 tool description 中注明所需权限，Agent 按当前用户角色决定是否注入该 Server 的 tools
2. **请求级** — 项目中 `MCPToolSession.reset_for_request()` 传入 user_id / conversation_id / agent_mode，MCP Server 端根据 user_id 做鉴权（如用户画像 Server 只返回当前用户的画像，不能跨用户查）
3. **Server 分组** — MCP Server 注册时按 server_name 分组，不同 agent_mode 加载不同 server 组合

**参数校验：**

- MCP 协议要求 Server 端对 parameters JSON Schema 做校验，不合法返回 JSON-RPC error
- 项目额外做：`ToolCallPolicy` 记录每次 tool_call 的 arguments，Guardrail 做重复检测
- 电商场景强化：price 必须 >0 且 ≤max_price，size 枚举约束，category 必须在有效类目树内——这些写在 MCP Server 的 inputSchema 约束里

**超时控制：**

1. **MCP 连接层** — `MCPConnectionPool` 初始化时有超时配置，连接建立超时自动断开
2. **工具执行层** — `ToolExecutor` 有执行超时（`asyncio.wait_for`），单个 tool_call 超时返回错误 tool_result
3. **全局兜底** — ReAct 循环的 `MAX_TOTAL_ITERATIONS`（普通模式 10 轮，Agent 模式 90 轮）+ `unified_context_guard` 的 token 阈值，双保险防止无限循环

---

#### Q3: MCP SSE 远程 vs stdio 本地 + Zalando 多租户选型

**两种传输方式：**

| 维度 | stdio（本地进程） | SSE（远程 HTTP） |
|------|-------------------|------------------|
| 启动方式 | Agent 进程 fork 子进程 | 独立 HTTP 服务 |
| 延迟 | 极低（进程间 IPC） | 取决于网络（几十~几百 ms） |
| 鉴权 | 无需（同进程信任） | 需 token/证书 |
| 多租户 | 每用户一个进程，资源开销大 | 多用户共享服务，按 token 鉴权 |
| 部署 | 工具代码必须跟 Agent 同机 | 工具独立部署、独立扩缩容 |
| 适合场景 | 本地文件操作、沙箱执行 | 商品搜索、库存等共享服务 |

**项目踩过的坑：**

1. **MCP 延迟** — stdio 模式下 MCP Server 冷启动慢（首次 fork + 初始化），项目做了连接池预热
2. **SSE 鉴权** — 远程 MCP Server 需要请求头携带 auth token，`MCPClientManager` 在连接建立时注入
3. **断连重连** — SSE 连接可能被 CDN/nginx 超时断开，需心跳保活 + 自动重连

**Zalando 多租户导购 Agent 推荐：**

- 商品搜索、库存、比价等共享服务 → **SSE 远程**（独立部署，多 Agent 共享，按租户鉴权）
- 用户数据操作（画像读写、订单查询）→ **SSE + 严格鉴权**（每个请求验证 user_id 权限）
- 沙箱代码执行 → **stdio 本地**（安全隔离，不能暴露给外部）

---

#### Q4: 四级上下文压缩集成到 MCP 服务层

**项目四级 `unified_context_guard`（`chat_session_agent.py:288`）：**

触发时机：每次 LLM 调用前，计算当前 messages 总 token 是否超过 threshold（`context_limit - max_output - buffer`）

**Step 1: token 检测** — 如果 `total_tokens ≤ threshold`，直接放行

**Step 2: 工具结果压缩** — `compress_history_tool_results()` 对历史 tool_result 做 head_tail 截断（保留头尾各若干字符，中间省略），减少 tool 输出占的 token

**Step 3: 滑动窗口 + 增量摘要** — `split_by_remaining_budget()` 把 history 分为 in_window（保留近期）+ out_of_window（早期消息），对 out_of_window 部分调 LLM 生成摘要，存储到 `summary_before_window`。带 anti-thrash 机制（防同一组消息反复摘要）

**Step 4: 工具轮次裁剪** — `tool_round_compressible_end()` 识别工具调用组（ToolUse + 连续 ToolResult），保护最近 N 组，压缩更早的工具轮次

**Step 5: 兜底** — 如果仍然超标，进一步收紧 `keep_recent_groups`，极端情况清空 out_of_window 摘要

**集成到 MCP 服务层的思路：**

不在 Agent 层做压缩，而是在 MCP Server 返回 tool_result 时就控制大小：

1. **MCP Server 端预截断** — 商品搜索返回 100 条 SKU，MCP Server 自己先按相关度排序截取 top 20，返回给 Agent 的 result 就已经精简
2. **MCP 协议层压缩中间件** — 在 `MCPClientManager` 收到 tool_result 后、返回给 Agent 前，加一层压缩：超长 result 自动做 head_tail 截断，类似项目 Step 2 但前置到 MCP 传输层
3. **摘要下沉** — 对 out_of_window 的工具调用历史，MCP Server 可以提供 `summarize` 工具，Agent 调它把长对话摘要为短文本
4. **好处** — Agent 层拿到的 tool_result 已经是合理大小，`unified_context_guard` 触发频率大幅降低，token 消耗减少

---

## 二、架构设计大题

### 2.1 后端分层架构

**Zalando 时尚电商个性化购物 Agent 分层：**

```
┌─────────────────────────────────────────────┐
│  前端（React SPA + SSE 实时流式）              │
├─────────────────────────────────────────────┤
│  BFF 层（FastAPI）                            │
│  ├─ SSE 流式端点（chat/completions）           │
│  ├─ 会话管理（CRUD + 历史）                    │
│  └─ 用户认证 + 租户隔离                       │
├─────────────────────────────────────────────┤
│  Agent 编排层（ChatSessionAgent 等价物）       │
│  ├─ ReAct 循环（多轮工具调用 + 最终回答）       │
│  ├─ 上下文守卫（四级压缩）                     │
│  ├─ 工具 Guardrail（熔断/防死循环）            │
│  └─ 记忆注入（mem0 前置检索 → system prompt）  │
├─────────────────────────────────────────────┤
│  工具层（MCP 协议标准化接入）                   │
│  ├─ 商品搜索 MCP Server                       │
│  ├─ 库存/尺码 MCP Server                      │
│  ├─ 穿搭推荐 MCP Server                       │
│  ├─ 价格对比 MCP Server                       │
│  ├─ 用户画像 MCP Server                       │
│  └─ 物流查询 MCP Server                       │
├─────────────────────────────────────────────┤
│  数据层                                       │
│  ├─ PostgreSQL + pgvector（商品向量 + 会话）    │
│  ├─ Redis（会话缓存 + SSE 消息续传 + 热点缓存）│
│  └─ mem0（跨会话用户偏好记忆）                 │
└─────────────────────────────────────────────┘
```

**对比 Shopee 项目：** 分层逻辑一致（BFF → Agent 编排 → MCP 工具 → 数据层），区别在于 Zalando 场景工具更多（6+ MCP Server），需要 MCP 连接池做管理；商品数据量大（百万 SKU），pgvector 需要分片和冷热分离。

---

### 2.2 RAG 商品检索设计

#### （a）短描述 vs 长图文详情的召回策略

| 文档类型 | 长度 | 策略 |
|---------|------|------|
| 短款服装描述（标题+属性） | <500 字符 | 直接注入 context，不做向量检索。类似项目"短文档直注"策略 |
| 长图文详情页 | >2000 字符 | 先用 MinerU/图片解析提取结构化文本 → 分块 → 向量化入库 → 检索时 top_k 召回 |

#### （b）pgvector 适配百万 SKU

1. **惰性索引** — 新商品先写入但不立即建 IVFFlat/HNSW 索引，定时批量 rebuild
2. **分片** — 按一级类目（女装/男装/鞋）分表，每张表独立向量索引，查询时先意图分类再路由到对应分片
3. **冷热分离** — 热销商品（近 30 天有浏览/购买）放 pgvector 主表，冷商品归档到独立表，检索时先查主表未命中再查冷表

#### （c）模糊穿搭意图的完整链路

用户输入："适合通勤的黑色显瘦连衣裙，预算 80 欧内"

```
1. 意图解析（LLM 结构化输出）:
   {category: "连衣裙", color: "黑色", style: "通勤",
    feature: "显瘦", max_price: 80, currency: "EUR"}

2. 硬约束过滤（确定性代码，不走 LLM）:
   SQL: WHERE category='连衣裙' AND color='黑色'
        AND price <= 80 AND currency='EUR'
   → 缩小候选集到可管理范围

3. 向量召回（语义匹配）:
   query_embedding = embed("适合通勤的显瘦连衣裙")
   → pgvector ANN 检索 top_k=8（项目最优配置）

4. 重排（Cross-encoder 或 LLM）:
   对 8 个候选按"通勤显瘦"语义相关度重排

5. 补充推荐:
   LLM 基于主推结果，调穿搭推荐工具补充搭配（外套/鞋/包）
```

关键设计点：硬约束（价格、尺码、颜色）用确定性代码过滤，语义理解（"显瘦""通勤"）交给向量检索 + LLM，分离"精确过滤"和"模糊理解"。

---

### 2.3 多轮对话上下文治理

**电商长会话特点：** 用户连续聊穿搭、比价、尺码筛选，20+ 轮对话很常见，工具调用结果（商品列表 JSON）体积大。

**四级守卫适配电商场景的调整：**

**Step 2 工具结果压缩 — 电商强化：**
- 商品列表 JSON 结果自动截断：只保留 name/price/rating/size 四个字段，丢弃 description/image_url 等大字段
- 类似项目的 `head_tail_truncate_chars`，但对商品结构化数据做字段级压缩

**Step 3 滑动窗口 + 增量摘要 — 保留关键偏好：**
- 摘要 prompt 中显式要求保留：用户尺码、预算范围、风格偏好、已排除的商品特征
- 例如：用户说"我不喜欢蕾丝"→ 摘要必须包含"排除:蕾丝"，否则后续推荐会重复推荐蕾丝款

**Step 4 工具轮次裁剪 — 电商场景：**
- 保留最近 2 组工具调用（最新搜索结果 + 最新尺码查询），压缩更早的搜索结果
- 被压缩的商品列表用摘要替代："已搜索过 5 次连衣裙，共浏览 35 款，排除了蕾丝和超过 80 欧的款式"

**避免压缩丢失关键偏好：**

用结构化偏好对象而非自然语言描述存关键信息：

```python
user_preferences = {
    "size": "M",
    "budget_max": 80,
    "style": ["通勤", "简约"],
    "excluded": ["蕾丝", "亮片"],
    "favorite_colors": ["黑色", "深蓝"]
}
```

这个对象独立于 conversation history 存储（类似 mem0 长期记忆），不参与窗口滑动，每次注入 prompt。

---

### 2.4 跨会话持久记忆

**mem0 用户级记忆方案：**

1. **存储维度：**
   - 穿搭偏好：风格、色系、尺码 → mem0 长期记忆
   - 历史浏览/加购：商品 ID + 时间戳 → mem0 记录（带 TTL，过季自动衰减）
   - 购买历史：订单号 + 商品 → mem0 长期记忆

2. **每次对话前置检索注入 prompt：**
   ```
   chat_orchestrator 发起请求前:
   → memory_service.get_memories(user_id)
   → 注入到 system prompt / user message 上下文区
   ```

3. **临时 vs 长期记忆区分：**

| 类型 | 存储位置 | 生命周期 | 示例 |
|------|---------|---------|------|
| 临时会话记忆 | `_working_history` + 当前对话 messages | 会话结束即丢 | "这次想看 50 欧以下的" |
| 长期用户画像 | mem0 REST API（持久化） | 跨会话，可更新 | "偏好 M 码，喜欢简约风" |

4. **避免记忆污染推荐：**
   - mem0 检索结果有 confidence score，低于阈值的不注入
   - 过季偏好自动衰减：存储时附带时间戳，检索时按时间加权（去年冬天的大衣偏好今年权重降低）
   - 用户主动修正优先：如果用户本轮说"预算改成 100 欧"，临时覆盖 mem0 的 80 欧记忆，但不立即持久化（防止一次对话中的临时需求污染长期画像）

---

### 2.5 工具生态设计

**Zalando 必备 7 个 MCP Server 工具：**

```
商品搜索 MCP Server:    search_products(query, category, price_range, size, color, style)
库存查询 MCP Server:    check_stock(product_id, size, color)
尺码推荐 MCP Server:    recommend_size(user_measurements, brand_id)
穿搭生成 MCP Server:    generate_outfit(base_item, occasion, style)
价格对比 MCP Server:    compare_prices(product_id, retailers)
物流查询 MCP Server:    track_shipment(order_id)
用户画像 MCP Server:    get_user_profile(user_id) / update_preferences(user_id, prefs)
```

**参数强校验（Pydantic model 约束写在 MCP Server 注册时）：**

```json
{
  "price_range": {"type": "object", "properties": {
    "min": {"type": "number", "minimum": 0},
    "max": {"type": "number", "maximum": 10000}
  }},
  "size": {"type": "string", "enum": ["XS","S","M","L","XL","XXL"]},
  "category": {"type": "string", "enum": ["dress","top","bottom","shoes","accessories"]}
}
```

**双层收敛机制（电商场景举例）：**

- **硬约束（确定性代码）：** `ToolCallGuardrail` 的 no_progress 检测 —— 如果模型连续 3 次调 `search_products` 传相同参数返回相同结果，BLOCK 并提示"请更换查询条件"。电商典型场景：模型反复搜"黑色连衣裙"不换词。
- **收敛提示（注入 prompt）：** 每轮 `iteration_hints` 注入当前搜索状态："你已搜索连衣裙 3 次、外套 1 次，共浏览 25 款商品。建议直接给出推荐总结，或尝试不同品类。"

**三层熔断防大促 Token 打爆：**

1. 精确参数重复 → ≥5 次 BLOCK（模型不要重复搜同款）
2. 同工具连续失败 → ≥8 次 HALT 全量熔断（商品 API 雪崩时快速止损）
3. 无进展检测 → ≥5 次相同结果 BLOCK（防止比价死循环）

额外加上：`MAX_TOTAL_ITERATIONS=10`（非 Agent 模式）作为全局限制，即使 guardrail 没触发也最多 10 轮工具调用。

---

### 2.6 SSE 流式导购交互

**实现方案（和项目对齐）：**

```
客户端 ←──SSE──→ FastAPI ←──→ ChatSessionAgent ←──→ MCP Tools
                        ↘──Redis Stream──→ 断连续传
```

1. FastAPI SSE 端点：`StreamingResponse(stream_session_events(), media_type="text/event-stream")`
2. 每个 SSE event 类型：`content_block`（文本片段）、`tool_call`（工具调用）、`tool_result`（工具结果）、`done`（结束）
3. Redis Stream 持久化：每条 event 写入 `stream:{conversation_id}:{turn_id}`，message_id 递增
4. 断连续传：客户端重连时带 `Last-Event-ID`，FastAPI 从 Redis Stream 读取该 ID 之后的消息补发

**对比 pydantic-ai 原生流式：**
- pydantic-ai `run_stream()` 是进程内流式，不自带断连续传
- 如果用 pydantic-ai 做 Zalando 导购，需要在 Agent 外层包一层 Redis Stream 持久化，和项目方案本质相同

---

### 2.7 安全沙箱与防护

**代码执行场景：** 商品数据分析（用户说"帮我对比这 3 款的性价比"）、图表生成（"画个价格趋势图"）。

**类比 Piston 沙箱方案：**

1. **沙箱隔离** — 代码在独立容器/进程中执行（Piston / CubeSandbox），无网络访问、无文件系统写入权限
2. **电商风险拦截：**
   - 批量爬取价格 → 沙箱禁止网络访问，只允许通过 MCP 工具查价格
   - 越权查用户订单 → 沙箱中无 user_id 上下文，查订单必须走 MCP 用户画像工具（带鉴权）
3. **资源限制** — 执行超时（10s）、内存上限（256MB）、输出大小限制（防止返回巨量数据撑爆上下文）

**高危操作人工审批：**

- 修改收藏、加入购物车 → 不需要审批（可撤销操作），但需二次确认（Agent 回复"确认要加入购物车吗？"）
- 下单、支付 → 必须跳转到前端确认页面，Agent 只提供链接不执行操作
- 删除收藏夹、清空购物车 → 需二次确认 + 用户 ID 校验

---

### 2.8 可观测与性能优化

**Langfuse 全链路 Trace：**

- 每次 Agent 请求创建 trace，span 覆盖：意图解析 → 向量检索 → 每次 tool_call → 最终回答
- 记录指标：工具调用次数、每次 tool_call 延迟、token 消耗（input/output）、上下文守卫是否触发及压缩比例

**项目优化手段迁移到 Zalando：**

| 项目的优化 | 迁移到 Zalando 导购 |
|----------|-------------------|
| 端到端延迟 -25% | 工具并行执行（独立的商品搜索+库存查询可并行）、向量检索缓存热门查询 |
| Token -30% | 工具结果字段级压缩（只保留 name/price/size）、上下文滑动窗口+增量摘要 |
| 上下文守卫减少溢出 | 电商场景工具结果体积更大，Step 2 压缩收益更高 |

**Prometheus 监控指标：**

```
# 工具维度
tool_call_duration_seconds{tool="search_products"} histogram
tool_call_failures_total{tool="search_products", reason="timeout"} counter

# Guardrail 维度
guardrail_halt_total counter          # 全量熔断次数
guardrail_block_total{reason="no_progress|exact_failure"} counter

# 向量检索
vector_search_duration_seconds histogram
vector_search_recall_count histogram   # 召回条数

# SSE 维度
sse_disconnect_total counter
sse_reconnect_total counter
sse_stream_duration_seconds histogram

# Token 维度
token_consumed_total{type="input|output"} counter
context_guard_trigger_total{step="2|3|4"} counter
```

---

### 2.9 对比/演进类架构追问

#### Q1: 单 Agent vs 多 Agent 并行

**项目现状：** 单 Agent 串行执行搜索 → 数据分析 → 图表生成。

**为什么要做多 Agent：**
- 串行执行时，搜索完等数据分析，分析完等图表生成，端到端延迟累加
- 电商复合场景（穿搭+比价+数据分析）更明显：三个子任务互不依赖，串行浪费时间

**多 Agent 分工：**

```
用户: "给我推荐几套通勤穿搭，对比价格，做个预算表"

主 Agent（编排）
├─ 检索 Agent: 并行搜索连衣裙+外套+鞋
├─ 推荐 Agent: 基于检索结果生成穿搭组合
└─ 数据分析 Agent: 价格对比 + 预算表格生成
→ 三个 Agent 并行执行，主 Agent 汇总结果
```

**收益：** 端到端延迟从 T1+T2+T3 降为 max(T1,T2,T3)，理论上降低 60%+。

---

#### Q2: PostgreSQL+pgvector vs 独立向量库

**选择 pgvector 的原因：**
- 项目已有 PostgreSQL 做会话/用户数据，pgvector 是 extension 不引入新组件
- SQL + 向量混合查询（WHERE category='dress' AND vector_similarity > 0.7）不需要跨库 JOIN
- 运维成本低，一个数据库搞定

**百万 SKU 瓶颈与扩容方案：**
- pgvector HNSW 索引在百万级 OK（查询 P99 < 100ms），千万级以上需要分片
- 扩容方案：按类目分表（每张表 < 100 万行）+ 读副本分担查询压力
- 如果真到亿级：上专用向量库（Qdrant/Milvus），但 pgvector 作为 hot path 的本地缓存层保留

---

#### Q3: 高并发大促削峰限流

**复用 GEO 项目 Kafka 经验：**

- **削峰：** 用户请求不直接打到 Agent，先写 Kafka topic，Agent 消费者按固定速率拉取处理
- **并发限流：** Redis 令牌桶（`user:{id}:tokens`），每用户每秒 N 次请求
- **任务调度：** Kafka consumer group 保证同一用户同一会话的消息顺序消费（partition key = conversation_id）
- **死信队列：** 处理失败 3 次的消息进 DLQ，人工排查后重放

---

## 三、简历深挖压力面

### Q1: Shopee AI 智能助手从 0 到 1 关键技术决策

1. **选 ReAct 而非纯 function calling** — 需要多轮工具调用+中间推理可见，ReAct Loop 更灵活
2. **选 MCP 协议标准化工具** — 多团队协作维护工具，MCP 统一了 tool schema + 执行协议，新增工具零改动 Agent 代码
3. **选 PostgreSQL+pgvector 而非独立向量库** — 减少运维组件，SQL+向量混合查询更自然
4. **自研上下文守卫而非用框架内置** — 电商长会话高频触发 token 溢出，需要精细的分级压缩策略
5. **SSE+Redis Stream 做流式** — 电商用户频繁切页面，断连续传是刚需

---

### Q2: 自研 ReAct Loop 完整执行链路

```
stream_session_events() 入口
│
├─ 1. 初始化: system_prompt + tools + history + memories
│
├─ 2. for iteration in range(MAX_ITERATIONS):
│   │
│   ├─ 2a. iteration_hints: 注入当前搜索状态提示（收敛引导）
│   │
│   ├─ 2b. unified_context_guard: token 超标 → 分级压缩
│   │
│   ├─ 2c. LLM 调用（流式）:
│   │   ├─ 有 tool_call → 解析参数 → guardrail 检查 → 并行执行 MCP tools
│   │   │   ├─ before_call: 精确重复/同工具失败/无进展 三层检查
│   │   │   ├─ 执行: MCPToolSession.execute_tool_calls_parallel()
│   │   │   └─ record_outcome: 更新计数器 + 注入警告
│   │   └─ 无 tool_call → 最终回答 round → yield SSE → return
│   │
│   └─ 2d. guardrail_halted? → 强制最终回答 round → return
│
└─ 3. 超过 MAX_ITERATIONS → 强制最终回答 round
```

**每一层解决的痛点：**

- `iteration_hints` → 解决模型反复搜同款不收敛
- `unified_context_guard` → 解决长会话 token 溢出
- `ToolCallGuardrail` → 解决工具死循环打爆 API
- `MAX_TOTAL_ITERATIONS` → 兜底防止无限循环

---

### Q3: MCP 工具标准化最难的 3 个技术问题

1. **工具路由与参数透传** — MCP Server 数量多了之后，LLM 选错工具或传错参数的概率上升。解决：tool description 写清楚用法+参数约束，加上 `iteration_hints` 引导。
2. **工具执行超时与错误处理** — MCP Server 可能慢响应或返回错误。解决：`ToolExecutor` 做超时控制+错误分类，timeout 返回友好错误消息给 LLM 自行重试。
3. **工具结果体积控制** — 某些工具返回巨量数据（如文件读取、数据库查询）。解决：`tool_result_hard_limit` 对结果做 head_tail 截断，配合 `unified_context_guard` Step 2 压缩。

---

### Q4: 四级上下文守卫触发条件与压缩逻辑

**真实案例：用户超长穿搭对话（25+ 轮）**

| 步骤 | 触发条件 | 操作 | 效果 |
|------|---------|------|------|
| Step 1 | total_tokens > threshold | 检测触发 | 进入压缩流程 |
| Step 2 | tool_result 体积大 | head_tail 截断历史 tool_result | token 降 ~30% |
| Step 3 | 仍然超标 | 滑动窗口切分 + LLM 增量摘要 | 早期对话压缩为摘要，token 降 ~50% |
| Step 4 | 仍然超标 | 压缩更早的工具轮次 | 工具调用历史缩减 |
| Step 5 | 极端情况 | 进一步收紧 keep_recent | 最后兜底 |

**优化前后对比：** 25 轮对话，优化前 ~18K tokens，触发 Step 2+3 后降到 ~10K tokens，不触发模型 context overflow 错误。

---

### Q5: 模型反复调用 web_search 无法收敛

**双层治理：**

1. **硬约束 — Guardrail：**
   - 第 3 次相同参数搜索 → ⚠️ 警告"请更换关键词"
   - 第 5 次 → BLOCK"已阻断，请换用其他工具或改变搜索词"
   - 第 8 次同工具连续失败 → HALT 全量熔断

2. **收敛提示 — iteration_hints：**
   - 每轮注入："你已搜索 3 次，共获得 15 条结果。建议基于已有信息直接回答。"
   - 第 5 轮额外注入："工具调用已达上限的一半，请尽快收敛。"

---

### Q6: mem0 记忆集成问题

**遇到的问题：**
1. mem0 REST API 延迟 ~200ms，每请求前置检索增加端到端延迟
2. 记忆过时：用户说"今年冬天喜欢长款"但 mem0 里存的是"去年喜欢短款"
3. 记忆冲突：临时偏好和长期画像矛盾时，推荐结果不稳定

**解决方案：**
1. 记忆检索并行化 — 与工具 schema 获取并行执行，不阻塞主链路
2. 时间衰减 — mem0 记忆带时间戳，检索时按 recency 加权，过季偏好自动降权
3. 临时优先 — 当前对话的显式偏好 > mem0 长期记忆，只在会话无显式偏好时回退到 mem0

---

### Q7: SSE 断连补偿 Redis Stream 设计

**设计细节：**

- Stream key: `sse:{conversation_id}:{turn_id}`
- 每条 SSE event 写入时：`XADD sse:{conv}:{turn} * event_type {data}`
- 客户端重连：带 `Last-Event-ID` 请求头 → 服务端 `XRANGE sse:{conv}:{turn} {last_id} +`
- 消息 TTL: 2 小时后自动过期（`EXPIRE`）

**线上效果：** 断连率从 ~8% 降到 ~1.5%（用户感知的"丢消息"基本消除）。

---

### Q8: Piston 代码沙箱安全双层模型

**第一层：沙箱本身隔离**
- Piston 容器无网络、无持久存储、内存 256MB 上限、执行超时 10s
- 用户代码只能操作传入的数据，无法访问外部服务

**第二层：Agent 层过滤**
- 代码执行前，ToolCallPolicy 检查：是否包含网络请求（requests/urllib）、文件操作（open/os）、子进程（subprocess）→ 拦截
- 执行结果做大小限制，防止返回 MB 级数据撑爆上下文

---

### Q9: Langfuse 定位的核心性能瓶颈

**发现的问题：**
1. 工具结果过大（单个 tool_result 平均 2K tokens）→ Step 2 压缩后降到 ~800 tokens
2. 上下文守卫未触发时，历史消息重复计算 token → 缓存 token 计算结果
3. MCP 工具串行执行 → 并行化独立工具

**量化收益：**
- 端到端延迟 -25%：工具并行 + token 计算缓存
- Token 消耗 -30%：工具结果压缩 + 滑动窗口摘要

---

### Q10: 最严重线上故障

**故障：** 用户连续 20+ 轮对话，第 18 轮触发 context overflow，模型返回空响应。

**根因：** 当时上下文守卫只有 Step 1（硬截断），没有分级压缩。

**止损：** 紧急加了 `MAX_TOTAL_ITERATIONS` 兜底限制。

**长效治理：** 开发了四级 `unified_context_guard`，分级降级而非硬截断。

---

### Q11: 如果重做，三处重构

1. **工具层全面 MCP 化** — 早期部分工具是硬编码在 Agent 里的，改为全部走 MCP Server，工具热更新零改动
2. **多 Agent 并行架构** — 单 Agent 串行是最大瓶颈，改为编排 Agent + 并行子 Agent
3. **记忆分层架构** — mem0 只做长期记忆，加一层短期会话记忆（Redis），避免 mem0 的延迟影响每轮对话

---

## 四、电商业务场景专项题

### Q1: 模糊意图完整执行链路

用户："推荐适合冬天、小个子、不超过 100 欧的大衣"

```
1. LLM 结构化输出:
   {category:"coat", season:"winter", height_profile:"petite", max_price:100, currency:"EUR"}

2. 硬约束 SQL 过滤:
   WHERE category='coat' AND season='winter' AND price<=100
   → 候选集从百万缩减到几百

3. 向量召回 top_k=8:
   embed("适合小个子的冬天大衣 短款 显高") → pgvector ANN

4. Cross-encoder 重排:
   对 8 个候选按"小个子显高"语义相关度排序

5. 搭配补充推荐:
   LLM 基于主推大衣，调 generate_outfit 工具推荐内搭+裤装+鞋

6. 结果格式化流式输出:
   SSE 推送：推荐大衣卡片 → 搭配建议 → 穿搭 tips
```

### Q2: 个性化转化提升

- 每次搜索前注入 mem0 用户偏好 → 向量检索的 query 用偏好增强："适合小个子 通勤 简约 的黑色连衣裙"（原始 query + 偏好关键词）
- 检索结果重排时加权：用户历史加购过的品牌权重 +0.3，历史浏览但未购买的风格权重 +0.1
- 动态调整策略：如果用户连续 3 次对话都没看推荐结果，自动降低推荐频率，改为直接回答问题

### Q3: 多模态穿搭图片

- 用户上传穿搭图片 → 调用 vision 模型（GPT-4V / Qwen-VL）提取：风格、主色系、款式、材质
- 提取结果结构化 → 作为 `search_products` 的参数："style=minimalist, color=black, material=cotton, category=dress"
- 向量检索相似商品 → 推荐同风格/同色系替代品

### Q4: 换季向量索引更新

- 新品上架：实时写入 pgvector（INSERT），不触发索引 rebuild
- 索引 rebuild：每天凌晨低峰期批量 rebuild HNSW/IVFFlat 索引
- 冷热分离：当季商品在主表，过季商品归档（每月一次迁移）
- 成本平衡：HNSW 索引 build 代价 O(N log N)，百万 SKU 约需 10-30 分钟，凌晨可接受

### Q5: 避免重复推荐去重

- 项目的 0.7 相似度去重机制：已推荐商品的 embedding 存入 session 临时缓存
- 新推荐候选的 embedding 与已推荐集合做 cosine similarity，≥0.7 的跳过
- 同时做 ID 级去重：同一会话中推荐过的 product_id 不再推荐

### Q6: 幻觉抑制

- **工具结果校验：** 库存/价格/尺码必须来自 MCP 工具返回，LLM 不能自行编造。如果 LLM 回答中包含商品信息但没有对应的 tool_call，标记为"未经验证"
- **向量召回兜底：** 如果 LLM 推荐了一个商品，但向量库中搜不到该商品 ID，自动过滤掉该推荐
- **双重抑制：** Agent 最终回答前，校验器检查每个推荐商品是否都有 tool_result 支撑，无支撑的删除并替换为"抱歉，该商品信息暂时无法确认"

---

## 五、分布式、稳定性、运维工程题

### Q1: 容器化 + 大促扩容

- Docker Compose 部署：Agent 服务（FastAPI）无状态，可水平扩 N 个副本
- 无状态改造关键：会话上下文存 Redis/DB 不存进程内存，SSE 消息存 Redis Stream
- 大促扩容：Kubernetes HPA 按 CPU/QPS 自动扩缩，或手动扩 FastAPI worker 数

### Q2: Redis 缓存分层

| 缓存层 | Key 格式 | TTL | 防护 |
|--------|---------|-----|------|
| 会话上下文 | `session:{conv_id}` | 2h | LRU 淘汰 |
| 热点 SKU | `sku:vector:{query_hash}` | 30min | 布隆过滤器防击穿 |
| 用户记忆 | `memory:{user_id}` | 1h | 主动失效（mem0 更新时） |

### Q3: Kafka 异步任务

- 商品索引构建：新品上架事件 → Kafka → 消费者异步调 embedding + 写 pgvector
- 用户记忆更新：对话结束事件 → Kafka → 消费者调 mem0 更新长期记忆
- 失败重试：exponential backoff，最多 3 次，失败进死信队列人工处理

### Q4: 质量门禁

- pre-commit hook：前端 `vp staged` + 后端 `uv run pre-commit run`（ruff lint + type check）
- pytest：工具调用逻辑单元测试（mock MCP Server）、Guardrail 边界测试
- CI 流水线：lint → test → build，全部通过才能合并

### Q5: 灰度发布

- 新 ReAct 逻辑：按 user_id hash 分桶，5% → 20% → 50% → 100%
- 新 MCP 工具：先在 staging 环境验证，然后通过 MCP Server 注册开关灰度启用
- 监控阈值：错误率 >1% 或 P99 延迟 >5s 自动回滚

---

## 六、开放性行为 & 技术选型压轴题

### Q1: pydantic-ai vs 自研 ReAct 迁移方案

**融合方案（不是替换）：**

- Agent 编排层保持自研（上下文守卫、Guardrail、SSE 流式是核心竞争力）
- 工具层用 MCP（已标准化，和 pydantic-ai 的 MCPToolset 兼容）
- 如果 Zalando 强制用 pydantic-ai：把 Guardrail 包装为 `@agent.tool` 装饰器内的 `ModelRetry` 逻辑，上下文守卫通过 `deps` 注入

### Q2: 技术演进路线

- **短期 3 个月：** 单 Agent + 工具完善（7 个 MCP Server 全量上线）+ 上下文守卫调优
- **中期 6 个月：** 多 Agent 并行（检索 Agent + 推荐 Agent + 数据分析 Agent），复合任务拆分
- **长期 1 年：** Agent 自我进化（根据用户反馈自动调整检索权重、工具选择策略）

### Q3: 智能灵活性 vs 稳定性

| 确定性代码（不交给 LLM） | LLM 推理（灵活决策） |
|------------------------|-------------------|
| 价格/尺码/库存过滤 | 意图理解、模糊需求解析 |
| Guardrail 熔断判断 | 工具选择策略 |
| 结果去重 | 穿搭推荐创意 |
| 上下文压缩执行 | 摘要生成 |
| 参数校验 | 多轮对话策略 |

### Q4: 评估指标

- **技术指标：** P99 延迟、token 消耗/会话、工具调用成功率、上下文守卫触发率
- **业务指标：** 推荐点击率、穿搭搭配保存率、咨询解决率（用户未转人工）、会话留存率

### Q5: 跨团队协作

- Agent 后端定义 BFF 接口契约（OpenAPI spec），前端按契约对接
- 各 MCP Server 团队按 MCP 协议规范独立开发，Agent 团队只需关注 tool schema 兼容性
- 推荐团队提供 embedding 模型 + 向量索引，Agent 团队通过 MCP 调用

---

## 七、高频反问

1. 当前 Zalando 导购 Agent 基于 pydantic-ai 落地了哪些核心工具（商品检索、穿搭生成等）？
2. 目前系统最大技术瓶颈是上下文超长、工具调用不稳定还是向量检索性能？
3. 团队是否规划做多 Agent 并行架构，处理穿搭+比价+数据分析复合任务？
4. 线上 LLM 成本、Token 消耗如何做预算管控与优化考核？
5. 导购 Agent 业务核心指标（穿搭推荐点击率、用户会话留存）当前基线与优化目标？
