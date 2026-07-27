# Mem0 记忆逻辑分析

基于 Mem0 Python SDK 源码的记忆系统架构分析。

## 版本对比

| 维度 | [v1.x](mem0-v1-memory-logic.md) | [v2](mem0-v2-memory-logic.md) |
|------|------|------|
| 版本 | v1.0.11 | v2.0.14 |
| LLM 调用 | 2 次（提取 + 决策） | 1 次（合并提取+决策） |
| 操作类型 | ADD / UPDATE / DELETE / NONE | 仅 ADD |
| 去重 | LLM 语义判断 | MD5 hash 精确匹配 |
| 检索方式 | 纯向量搜索 | 向量 + BM25 + entity boost |
| 记忆关联 | 无 | linked_memory_ids |
| 实体链接 | 无 | 自动提取 + entity store |

## 文档索引

- [v1.x 方案](mem0-v1-memory-logic.md) — 两次 LLM 调用，支持 ADD/UPDATE/DELETE，每条 fact 独立检索
- [v2 方案](mem0-v2-memory-logic.md) — 单次 LLM 调用，ADD-only，三路融合检索，实体链接
- [v1→v2 升级文档](mem0-v1-to-v2-upgrade.md) — 官方博客、论文、迁移指南汇总
- [Platform 增值方案](mem0-platform-decay-and-temporal.md) — Memory Decay 与 Temporal Reasoning 实现原理（OSS 未实现）
