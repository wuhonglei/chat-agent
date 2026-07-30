# RAG 测试集生成流程

## 概述

测试集采用 **LLM 生成 + 自动补全** 两阶段流程，覆盖三个难度级别：

| 难度 | 题型 | 来源 | 每个文件/对 |
|------|------|------|-------------|
| L1 | 简单事实题 | 单文档，答案可直接从文档中找到 | 3 题 |
| L2 | 推理归纳题 | 单文档，需要分析、比较或总结 | 2 题 |
| L3 | 跨文档综合题 | 需同时涉及两篇文档才能完整回答 | 2 题 |

## 阶段 1：LLM 生成问答对

脚本：`scripts/generate_testset.py`

### L1 + L2（单文档）

遍历 `files_new/*.md`，对每个文件调用 LLM 一次性生成 5 个问答对（3 L1 + 2 L2）。

- 文档超长时截取前 8000 字
- 文档类型分 `text`（原始文本）和 `scanned`（扫描件解析）
- L1 和 L2 共用同一个 prompt，通过难度描述约束区分
- 每条记录包含：`id`、`difficulty`、`question`、`ground_truth`、`source_file`、`doc_type`

### L3（跨文档）

手动定义 6 对跨文档组合（`L3_PAIRS`），每对各截取前 4000 字，生成 2 个跨文档问题。

当前 L3 组合：

| 文档 A | 文档 B | 关联主题 |
|--------|--------|----------|
| 房屋租赁合同_叶慧_20250901.md | 房屋租赁合同_杨君华_20250301.md | 两份租赁合同条款对比 |
| AI_Agent_Framework_Analysis_Report.md | 多Agent系统子Agent创建方式深度调研报告.md | AI Agent 框架与多 Agent 架构 |
| 吴洪磊简历.md | 协商一致解除劳动合同协议.md | 简历与劳动合同雇佣信息 |
| 吴洪磊 2023 纳税明细.md | 协商一致解除劳动合同协议.md | 纳税收入与劳动合同薪资 |
| MarkItDown vs MinerU vs Docling 对比报告.md | 运维常见问题详细解决方案.md | 技术方案选型与运维实践 |
| 吴洪磊简历.md | 体检报告-25091100056.md | 简历与体检报告身份信息 |

### 输出

`data/csv/testset_new_raw.csv`

## 阶段 2：补充 source_snippet

脚本：`scripts/enrich_testset.py`

为每条记录从源文档中提取 `source_snippet`（答案所在的原文片段），纯文本匹配，不调用 LLM。

匹配策略（按优先级）：

1. **精确子串匹配**：ground_truth 直接出现在原文中，取前后 500 字
2. **关键片段匹配**：按句号拆分 ground_truth，找包含最多片段的段落及其上下段
3. **关键词密度匹配**：提取中文词/英文词/数字，按关键词密度打分（数字权重 ×3）
4. **兜底**：直接使用 ground_truth 作为 snippet

### 输出

`data/csv/testset_new.csv`

## 最终测试集

多个批次的测试集合并为 `data/csv/testset_merged.csv`（当前 317 条）。

字段说明：

| 字段 | 说明 |
|------|------|
| `id` | 唯一标识，格式如 `l1-文档名_前15字-01` |
| `difficulty` | L1 / L2 / L3 |
| `question` | 问题 |
| `ground_truth` | 标准答案 |
| `source_file` | 源文件名（L3 用 `;` 分隔多个文件） |
| `doc_type` | text / scanned / cross |
| `source_snippet` | 答案所在的原文片段 |

## 当前分布

| 难度 | 条数 | 占比 |
|------|------|------|
| L1 | 174 | 54.9% |
| L2 | 103 | 32.5% |
| L3 | 40 | 12.6% |
| **合计** | **317** | **100%** |

## 运行方式

```bash
# 阶段 1: 生成问答对
python scripts/generate_testset.py

# 阶段 2: 补充 source_snippet
python scripts/enrich_testset.py
```
