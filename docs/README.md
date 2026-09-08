# 项目文档索引

本文档用于统一导航仓库内的业务/设计文档，避免与代码实现脱节。

## 如何使用本索引

- `现网实现`：与当前代码结构和接口保持一致，可直接按文档操作。
- `规划方案`：用于设计讨论，未必已经全部实现。
- `历史文档`：保留背景信息，不作为当前实现依据。

## 根目录文档（`/docs`）

### 现网实现

- `requirements.md`：当前版本需求范围与功能边界
- `认证流程.md`：短信/微信登录与 JWT 鉴权流程
- `会话管理.md`：会话列表/搜索（标题 ILIKE + 正文 zhcfg 全文检索）、草稿激活、手动压缩、消息（含 `full_content` / `content_text` / `llm_rendered_text` 固化与 API 剥离）、反馈入 Bad Case、聊天 SSE、`<current_datetime>` 冻结、Agent 迭代检查点（`task_action`）、断线续流与 Nginx 超时约定
- `CONVERSATION_SEARCH_OPTIMIZATION.md`：会话搜索索引（`content_text` / `content_tsv`）、`plainto_tsquery('zhcfg')`、zhparser 镜像与触发器排障
- `cache_design.md`：L1/L2 缓存现网范围、fail-open 行为、配置与排障
- `图表可视化展示.md`：图表渲染相关说明
- `nginx-cache-analysis.md`：Nginx 缓存分析
- `messages表字段精简计划.md`：消息表现网字段、已下线字段与排障核验
- `agent_observability/langfuse_integration.md`：Langfuse 自托管接入、trace 约定、`report_images` 脱敏、score 同步脚本与排障手册
- `agent_evaluator/rule_evaluator_design.md`：实时规则评估器指标与告警（含现网对接说明）
- `/backend/README.md`：聊天附件链路（图片/PDF/Excel/Markdown/文本文件）、v4 上传存储、普通模式 RAG 与 Agent 模式文件读取、代码执行 API、聊天 SSE 事件约定
- `/frontend/README.md`：Chat 内容块/附件约束、侧栏预览矩阵、文件 diff 展示、SSE 事件约定

### 规划方案

- `conversation-management-requirements.md`：会话管理需求（现网实现 + 规划项混合）
- `history-datetime-injection-plan.md`：历史 user 消息补时间（未落地）；文首「现网实现摘要」记录当前轮 `created_at` 冻结
- `phase0-sandbox-and-vfs-plan.md`：Sandbox/VFS 规划与阶段性落地记录；其中 uploads provider 已按当前实现补充为文件系统扫描
- `agent-mode-switch-plan.md`：Agent 模式开关历史改造计划；开头包含当前实现差异摘要，不作为逐步改造清单执行
- `agent_evaluation_framework.md`：评估框架早期盘点（部分表格已过时）；现网运维以 `/backend/docs/EVAL_OPS.md` 为准
- `agent_evaluator/agent_evaluation_plan.md`：四维评估体系规划稿

## 后端文档（`/backend/docs`）

### 现网实现

- `logging_guide.md`：结构化日志使用指南
- `type_checking_guide.md`：类型检查说明
- `用户管理.md`：用户模块、短信 Redis 鉴权与 Mem0 记忆集成（Platform v3 / 自建 OSS 路径分流、默认 `search_limit` / `search_threshold`）
- `EVAL_OPS.md`：评估 Worker、Bad Case 复核队列、CI 门禁 / replay 运维手册
- `COMPONENT_TOOLS_PRD.md`：组件工具接入说明（已对齐当前字段）
- `MCP_CONFIG_ANALYSIS.md`：MCP 配置与加载机制、工具命名双轨与唯一 bare 别名回退
- `VFS_AND_SANDBOX.md`：Agent 模式虚拟文件系统、file/shell MCP（工具 `exec`）、沙箱执行与排障手册
- `TOOL_RESULT_AND_CONTEXT.md`：工具结果硬上限、统一上下文守卫、窗口外摘要、手动全量压缩与 `last_summarized_message_ids`
- `LLM_RELIABILITY.md`：LLM 建连重试、错误分类与进程级熔断手册
- `PROMETHEUS_METRICS.md`：`/metrics` 暴露、无 `--preload` 的 Gunicorn multiprocess 约定与自定义进程指标
- `SLO.md`（`backend/docs/SLO.md`）：HTTP 可用性 SLO、错误预算与导入现有 Prometheus 平台的规则说明（`deploy/prometheus/`）
- `RETRIEVAL_SYSTEM.md`：当前检索链路说明（基于 MCP 工具与会话流）

### 规划方案

- `batch_eval_worker_design.md`：分层采样评估 Worker 方案稿；文首「现网实现摘要」对齐代码，运维步骤见 `EVAL_OPS.md`
- `目录结构优化建议.md`：目录结构优化建议

### 历史文档

- `USER_DATA_DIRECTORIES.md`：外部项目目录约定说明（本项目当前未使用）
- `confluence.md`：Confluence 相关历史设计
- `install_postgresql_mac.md` / `install_postgresql_centos.md`：环境安装参考
- `生成非对称密钥.md`：密钥生成脚本说明

## 前端文档（`/frontend/docs`）

### 现网实现

- `conversation.md`：会话路由、草稿激活、侧栏压缩、搜索（⌘K）、问题导航时间轴、检查点续跑与接口说明（对齐 `/api/conversation/*`）
- `schema-for-backend-usage.md`：前端聊天请求体字段（含 `taskAction`）与后端消费说明
- `conversion_cache.md`、`scroll-properties-explanation.md`、`aegis-埋点分析.md`

### 历史文档

- `component-tools-implementation.md`：组件工具旧链路历史归档
- `schema-generation.md`：旧 schema 脚本生成方式说明
- `vite-preview-cjs-esm-interop-memory.md`：历史排障记录（命令已按 Vite+ 更新）
- `知识点.md`、`项目依赖与Cursor-Agent-Skills分析.md`：知识沉淀/分析类文档

## 主入口文档

- 根项目说明：`/README.md`
- 后端说明：`/backend/README.md`
- 前端说明：`/frontend/README.md`
