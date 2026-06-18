# 5 份 Agent JD 知识点优先级总结

## 岗位概览

| 文件编号 | 岗位名称                   | 薪资         |
|----------|----------------------------|--------------|
| 01       | Agent 开发                 | 40-70K·15薪  |
| 04       | AI Agent 全栈开发工程师     | 20-40K       |
| 06       | Agent 前端开发工程师        | 20-40K       |
| 07       | AI Agent 工程师 (xTool)    | 20-40K·14薪  |
| 14       | AI Agent 工程师 (光子跃动)  | 30-60K       |

---

## A 级 — 核心必备（5/5 或 4/5 JD 提及，权重极高）

### 1. Agent 核心机制 [5/5]
- Tool Calling / Function Calling
- 任务规划与执行（Planning & Execution）
- 多轮交互 / 状态管理
- Agent Harness（上下文工程、错误恢复）

### 2. RAG + 向量数据库 [4/5]
- Embedding + 向量检索（pgvector / Milvus / Pinecone）
- 检索、召回、重排（Rerank）链路
- 知识库 / 规则库 / 商品库对接

### 3. LLM 大模型 API + Prompt Engineering [5/5]
- Claude / OpenAI / Gemini API 实战
- Token 管理、上下文窗口管理
- 结构化 Prompt 设计（可复用、有体系）

### 4. 多 Agent 协作架构 [4/5]
- 多 Agent 编排与调度
- Agent 间通信与任务分工
- LangGraph / CrewAI / ReAct / OODA 等推理模式

### 5. Python 后端工程 [5/5]
- FastAPI / Flask 等 Web 框架
- API / Webhook / 数据管道开发
- 高并发、分布式系统实战

### 6. PostgreSQL + 数据库设计 [4/5]
- 表结构设计、事务、并发、迁移
- Redis 缓存
- 向量库集成

### 7. 可观测性与监控 [4/5]
- 日志、指标、Trace、告警
- 成本监控与延迟优化
- 异常排查与问题复盘

---

## B 级 — 重要加分（3/5 JD 提及，区分度高）

### 8. 记忆与上下文管理系统 [3/5]
- 长程记忆 / 短期会话记忆
- 上下文窗口压缩与管理

### 9. Agent 评测体系 (Eval) [3/5]
- 效果评估基准设计
- A/B 测试、灰度发布
- 自动化回归机制

### 10. 工程化部署与运维 [3/5]
- Docker / K8s
- 缓存、限流、降级熔断、超时控制
- 阿里云 / 腾讯云产品

### 11. SSE / WebSocket 实时通信 [3/5]
- 流式数据渲染（Streaming）
- Server-Sent Events 原理与实现
- 增量更新

### 12. 成本优化与延迟控制 [3/5]
- 端到端延迟（TTFR）优化
- 规则 / 语义 / 模型多层分流
- 智能降级与兜底策略

### 13. AI 辅助开发工具 [3/5]
- Cursor / Copilot / OpenCode 实战
- AI Coding 工作流提效

### 14. 小模型微调 (SFT / DPO) [3/5]
- 数据构造、训练、评测闭环
- 适用于对效果有极致要求的场景

---

## C 级 — 了解即可（1-2/5 JD 提及，按方向选择）

### 15. MCP / A2A 等 Agent 互操作协议 [2/5]
- Model Context Protocol
- Agent-to-Agent 标准化通信

### 16. 前端组件体系 (React/Vue/TS) [1/5，但 06 号核心]
- 组件库设计与开发
- 在线文档编辑（OnlyOffice / Univer）

### 17. 混合 App / WebView / 原生桥接 [1/5]
- Swift 原生桥接
- Hybrid App 开发

### 18. 业务场景理解 [2/5]
- 客服 / 电商 / 跨境领域经验
- 飞书 / 多维表格等 B 端系统对接

### 19. 语音交互（ASR → LLM → TTS）[1/5]
- 实时语音对话系统
- 打断、超时等复杂交互

### 20. 端侧 / 具身 Agent [1/5]
- VLA、IoT / ROS 联动
- 属于前沿探索方向

---

## 知识图谱速查（按学习路径排序）

### 第一阶段：打地基
Python + FastAPI → PostgreSQL → LLM API 调用 → Prompt Engineering

### 第二阶段：Agent 核心
RAG (Embedding + 向量库 + Rerank) → Tool Calling → 任务规划 → 状态管理 / 上下文工程

### 第三阶段：工程化
SSE/Streaming → 可观测性(日志/监控/告警) → 成本优化 → Docker/K8s 部署 → 高并发与分布式

### 第四阶段：进阶区分
多 Agent 协作 → 记忆系统 → Eval 评测体系 → MCP/A2A 协议 → 小模型微调

### 第五阶段：前沿探索
语音交互 Agent → 端侧/具身 Agent → Agent 平台 0→1 搭建

---

## 关键洞察

- **5 份 JD 的最大公约数**：Agent 核心机制 + RAG + LLM API + Python 后端
- **高薪岗位（40K+）额外看重**：系统架构设计、成本控制、多 Agent 协作
- **全栈岗位额外看重**：前端工程体系（React/TS）、SSE 流式、组件开发
- **Agent 评测 (Eval) 正在成为标配能力**，不再是纯加分项
- **MCP / A2A 虽然只出现在 2 份 JD**，但属于 Agent 生态趋势，值得提前布局
