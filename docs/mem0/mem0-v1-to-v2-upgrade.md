# Mem0 v1 → v2 升级文档汇总

## 1. 官方变更日志（最重要的入口）

`docs/changelog/highlights.mdx` 中有一条 **2026-04-14** 的发布记录：

> **"New Memory Algorithm: State-of-the-Art Accuracy at ~3-4x Lower Cost"**

核心内容：
- LoCoMo 71.4 → 91.6 (+20)
- LongMemEval 67.8 → 93.4 (+26)
- BEAM (1M tokens) 64.1
- Agent memories 召回 46% → 100%
- 时序推理 51% → 93%
- token 用量从 25K+ 降到 <7K
- **BREAKING**: 外部图存储（Neo4j/Memgraph/Kuzu/Apache AGE）全部移除，改为内置 entity linking
- 引用了迁移指南：`/migration/oss-v2-to-v3`

来源：https://github.com/mem0ai/mem0/blob/master/docs/changelog/highlights.mdx

## 2. 官方博客（深度解读算法变更）

### 《Introducing The Token-Efficient Memory Algorithm》

https://mem0.ai/blog/mem0-the-token-efficient-memory-algorithm

详细解释了为什么要重写：

- **v1 问题**：两次 LLM 调用（提取 + 决策 ADD/UPDATE/DELETE），模型既要提取事实又要决定如何与已有记忆协调，导致延迟高、token 浪费大
- **v2 方案**：单次 LLM 调用，仅 ADD。LLM 只负责提取，冲突解决交给确定性下游系统（hash 去重 + entity linking）
- **效果**：提取延迟减半，token 成本降 3-4x，准确率反而大幅提升

### 后续更新博客

- https://mem0.ai/blog/the-token-efficient-memory-algorithm-now-has-temporal-reasoning （2026年5月，新增时序推理 + 记忆衰减）

## 3. 学术论文

**ArXiv: 2504.19413**
https://arxiv.org/html/2504.19413v1

《Mem0: Building Production-Ready AI Agents with Scalable ...》

- 2025年4月发表，基准测试覆盖 LOCOMO 数据集
- p95 延迟降低 91%，token 成本节省 90%+
- 与6类基线系统对比

## 4. 仓库内的迁移指南

Highlights 中引用了 `/migration/oss-v2-to-v3`，这是专门的迁移文档。另外仓库里还有：

- `scripts/oss-to-platform-migrate.sh` — 数据迁移脚本
- `skills/mem0-oss-to-platform/` — 从 OSS 迁移到 Platform 的自动化技能

## 5. v1→v2 升级解决了什么问题

| 问题 | v1 状态 | v2 解决方案 |
|------|---------|-------------|
| LLM 调用次数多 | 2 次（提取+决策） | 1 次（仅提取） |
| token 成本高 | 25K+ | <7K（降 3-4x） |
| 去重不可靠 | LLM 语义判断 | MD5 hash 精确匹配 |
| 检索单一 | 纯向量 | 向量 + BM25 + entity boost 三路融合 |
| 需要外部图存储 | Neo4j/Memgraph 等 | 内置 entity linking，无需外部依赖 |
| Agent 记忆召回率低 | 46% | 100% |
| 时序推理差 | 51% | 93% |
