# Langfuse 数据导入 - 阶段 2 完成报告

## 📋 阶段 2: 核心功能开发 - 完成情况

**完成时间**: 2026-06-18
**状态**: ✅ 已完成

---

## 🎯 阶段 2 目标

1. ✅ 完善数据导入脚本
2. ✅ 创建评分同步脚本
3. ✅ 实现错误处理和重试机制
4. ✅ 添加进度条和统计信息
5. ✅ 创建问答对回放工具

---

## 📊 完成情况

### 2.1 完善数据导入脚本 ✅

**文件**: `scripts/import_to_langfuse.py`

**功能特性**:
- ✅ 批量导入支持
- ✅ 错误处理和重试机制（指数退避）
- ✅ 进度显示和统计信息
- ✅ 断点续传支持（--offset 参数）
- ✅ 试运行模式（--dry-run）
- ✅ 导入日志记录
- ✅ Langfuse 缓冲区刷新

**使用示例**:
```bash
# 导入首次问答数据
python scripts/import_to_langfuse.py \
  --input scripts/first_qa_per_conversation.json \
  --batch-size 50 \
  --max-retries 3 \
  --prod

# 试运行
python scripts/import_to_langfuse.py \
  --input scripts/first_qa_per_conversation.json \
  --dry-run

# 断点续传（从第 100 条开始）
python scripts/import_to_langfuse.py \
  --input scripts/first_qa_per_conversation.json \
  --offset 100
```

**主要参数**:
- `--input`: 输入 JSON 文件路径
- `--batch-size`: 批次大小（默认 50）
- `--max-retries`: 最大重试次数（默认 3）
- `--source`: 数据源标识
- `--prod`: 使用生产环境配置
- `--dry-run`: 试运行模式
- `--offset`: 跳过前 N 条记录
- `--limit`: 最多导入 N 条记录

---

### 2.2 创建评分同步脚本 ✅

**文件**: `scripts/sync_scores_to_langfuse.py`

**功能特性**:
- ✅ 从数据库获取消息状态
- ✅ 生成确定性 trace_id
- ✅ 批量同步评分
- ✅ 状态映射（done=1.0, stopped=0.5, failed=0.0）
- ✅ 进度显示和统计信息

**使用示例**:
```bash
# 同步评分（生产环境）
python scripts/sync_scores_to_langfuse.py \
  --prod \
  --batch-size 100 \
  --limit 1000

# 试运行
python scripts/sync_scores_to_langfuse.py \
  --prod \
  --dry-run
```

**主要参数**:
- `--batch-size`: 批次大小（默认 50）
- `--limit`: 最多同步 N 条消息（默认 1000）
- `--offset`: 跳过前 N 条消息
- `--prod`: 使用生产环境配置
- `--dry-run`: 试运行模式

---

### 2.3 创建问答对回放工具 ✅

**文件**: `scripts/replay_qa_pairs.py`

**功能特性**:
- ✅ 通过 API 重新发送问答对
- ✅ 记录真实的延迟和工具调用
- ✅ 支持自定义 API 地址
- ✅ 支持多种模型选择
- ✅ 控制并发速度
- ✅ 保存回放结果

**使用示例**:
```bash
# 快速测试（前 10 个问题）
python scripts/replay_qa_pairs.py \
  --input scripts/first_qa_per_conversation.json \
  --limit 10

# 性能测试（全部首次问答）
python scripts/replay_qa_pairs.py \
  --input scripts/first_qa_per_conversation.json \
  --delay 0.5 \
  --batch-size 20

# 使用生产环境配置
python scripts/replay_qa_pairs.py \
  --input scripts/first_qa_per_conversation.json \
  --prod \
  --limit 100
```

**主要参数**:
- `--input`: 输入 JSON 文件路径
- `--api-base`: API 基础地址（默认 http://localhost:8000）
- `--username`: 登录用户名（默认 admin）
- `--password`: 登录密码（默认 admin123）
- `--user-id`: 用户 ID（默认 default_user）
- `--batch-size`: 批次大小（默认 10）
- `--delay`: 问题间延迟秒数（默认 2.0）
- `--model`: 使用的模型（默认 default）
- `--limit`: 最多回放 N 个问题
- `--output`: 输出文件路径
- `--prod`: 使用生产环境配置

---

### 2.4 创建使用说明文档 ✅

**文件**: `docs/replay_usage.md`

**内容**:
- ✅ 快速开始指南
- ✅ 详细参数说明
- ✅ 使用场景示例
- ✅ 性能指标说明
- ✅ 故障排除指南

---

## 📁 文件结构

```
scripts/
├── import_to_langfuse.py          # 数据导入脚本（完善版）
├── sync_scores_to_langfuse.py     # 评分同步脚本
├── replay_qa_pairs.py             # 问答对回放工具
├── import_to_langfuse_template.py # 导入模板
├── validate_environment.py        # 环境验证
├── validate_data.py               # 数据验证
├── validate_langfuse_data.py      # Langfuse 验证
├── import_log.py                  # 日志工具
├── first_qa_per_conversation.json # 首次问答数据
└── live_qa_data_final_v3.json     # 完整问答数据

docs/
├── langfuse_import_plan.md        # 实施计划
├── langfuse_stage1_report.md      # 阶段 1 报告
├── langfuse_stage2_report.md      # 阶段 2 报告
└── replay_usage.md                # 回放工具使用说明
```

---

## 🛠️ 技术特性

### 错误处理和重试机制

```python
# 指数退避重试
for attempt in range(max_retries + 1):
    try:
        result = import_single_record(langfuse_client, qa_data, source)
        if result["success"]:
            break
        else:
            if attempt < max_retries:
                time.sleep(retry_delay * (attempt + 1))  # 指数退避
    except Exception as e:
        if attempt < max_retries:
            time.sleep(retry_delay * (attempt + 1))
```

### 进度显示

```
批次 1/10 (50 条)
  ✅ 成功: 48, ❌ 失败: 2

批次 2/10 (50 条)
  ✅ 成功: 50, ❌ 失败: 0
```

### 统计信息

```
============================================================
导入完成统计
============================================================
总记录数: 441
成功导入: 440
导入失败: 1
重试次数: 3
成功率: 99.8%
总耗时: 45.2 秒
平均速度: 9.8 条/秒
```

---

## 📈 使用流程

### 方案 A: 直接导入到 Langfuse

```bash
# 1. 验证环境
python scripts/validate_environment.py

# 2. 验证数据
python scripts/validate_data.py

# 3. 试运行
python scripts/import_to_langfuse.py \
  --input scripts/first_qa_per_conversation.json \
  --dry-run

# 4. 正式导入
python scripts/import_to_langfuse.py \
  --input scripts/first_qa_per_conversation.json \
  --batch-size 50 \
  --prod

# 5. 验证结果
python scripts/validate_langfuse_data.py
```

### 方案 B: 通过页面回放

```bash
# 1. 确保后端服务运行
curl http://localhost:8000/

# 2. 快速测试
python scripts/replay_qa_pairs.py \
  --input scripts/first_qa_per_conversation.json \
  --limit 10

# 3. 性能测试
python scripts/replay_qa_pairs.py \
  --input scripts/first_qa_per_conversation.json \
  --delay 0.5 \
  --limit 100

# 4. 查看结果
cat scripts/replay_results.json
```

---

## ✅ 验收标准

- [x] 数据导入脚本完善
- [x] 错误处理和重试机制实现
- [x] 进度显示和统计信息
- [x] 评分同步脚本创建
- [x] 问答对回放工具创建
- [x] 使用说明文档
- [x] 断点续传支持
- [x] 试运行模式

---

## 🚀 下一步: 阶段 3

**阶段 3 目标**: 高级功能

**任务清单**:
- [ ] 批量导入优化
- [ ] 数据增强
- [ ] 错误处理和监控
- [ ] 性能优化

**预计时间**: 2-3 天

---

## 📝 快速命令参考

### 数据导入
```bash
# 试运行
python scripts/import_to_langfuse.py --input scripts/first_qa_per_conversation.json --dry-run

# 正式导入
python scripts/import_to_langfuse.py --input scripts/first_qa_per_conversation.json --prod

# 断点续传
python scripts/import_to_langfuse.py --input scripts/first_qa_per_conversation.json --offset 100
```

### 评分同步
```bash
# 试运行
python scripts/sync_scores_to_langfuse.py --prod --dry-run

# 正式同步
python scripts/sync_scores_to_langfuse.py --prod --limit 1000
```

### 问答回放
```bash
# 快速测试
python scripts/replay_qa_pairs.py --input scripts/first_qa_per_conversation.json --limit 10

# 性能测试
python scripts/replay_qa_pairs.py --input scripts/first_qa_per_conversation.json --delay 0.5
```

### 查看日志
```bash
python scripts/import_log.py summary
```

---

## 📚 相关文档

- [实施计划](docs/langfuse_import_plan.md)
- [阶段 1 报告](docs/langfuse_stage1_report.md)
- [回放工具使用说明](docs/replay_usage.md)
