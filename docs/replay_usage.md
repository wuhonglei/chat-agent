# 问答对回放工具使用说明

## 📋 概述

回放工具通过 API 重新发送历史问答对，可以：
- 测试系统性能和稳定性
- 记录真实的延迟和工具调用数据
- 验证系统功能是否正常
- 生成性能基准数据

---

## 🚀 快速开始

### 1. 确保后端服务运行

```bash
# 检查后端服务状态
curl http://localhost:8000/

# 如果未运行，启动后端服务
cd /Users/apple/Desktop/code/chat-agent/backend
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 2. 运行回放脚本

```bash
# 回放首次问答数据（前 10 个问题）
python scripts/replay_qa_pairs.py \
  --input scripts/first_qa_per_conversation.json \
  --limit 10

# 回放完整问答数据（前 20 个问题）
python scripts/replay_qa_pairs.py \
  --input scripts/live_qa_data_final_v3.json \
  --limit 20

# 使用生产环境配置回放
python scripts/replay_qa_pairs.py \
  --input scripts/first_qa_per_conversation.json \
  --prod \
  --limit 50
```

---

## 📖 详细用法

### 基本参数

```bash
python scripts/replay_qa_pairs.py \
  --input <输入文件> \
  --api-base <API地址> \
  --username <用户名> \
  --password <密码> \
  --user-id <用户ID> \
  --batch-size <批次大小> \
  --delay <延迟秒数> \
  --model <模型名称> \
  --limit <限制数量> \
  --output <输出文件> \
  --prod
```

### 参数说明

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--input` | 必需 | 输入 JSON 文件路径 |
| `--api-base` | http://localhost:8000 | API 基础地址 |
| `--username` | admin | 登录用户名 |
| `--password` | admin123 | 登录密码 |
| `--user-id` | default_user | 用户 ID |
| `--batch-size` | 10 | 批次大小 |
| `--delay` | 2.0 | 问题间延迟秒数 |
| `--model` | default | 使用的模型 |
| `--limit` | 0 | 最多回放 N 个问题 (0=全部) |
| `--output` | scripts/replay_results.json | 输出文件路径 |
| `--prod` | false | 使用生产环境配置 |

---

## 📊 使用场景

### 场景 1: 快速测试（前 10 个问题）

```bash
python scripts/replay_qa_pairs.py \
  --input scripts/first_qa_per_conversation.json \
  --limit 10 \
  --delay 1.0
```

**目的**: 快速验证系统功能是否正常

### 场景 2: 性能测试（全部首次问答）

```bash
python scripts/replay_qa_pairs.py \
  --input scripts/first_qa_per_conversation.json \
  --delay 0.5 \
  --batch-size 20
```

**目的**: 测试系统在连续请求下的性能

### 场景 3: 压力测试（全部问答数据）

```bash
python scripts/replay_qa_pairs.py \
  --input scripts/live_qa_data_final_v3.json \
  --delay 0.2 \
  --batch-size 50
```

**目的**: 测试系统在高并发下的稳定性

### 场景 4: 生产环境测试

```bash
python scripts/replay_qa_pairs.py \
  --input scripts/first_qa_per_conversation.json \
  --prod \
  --limit 100 \
  --delay 1.0
```

**目的**: 在生产环境中验证系统性能

---

## 📈 输出结果

### 控制台输出

```
============================================================
问答对回放工具
============================================================
输入文件: scripts/first_qa_per_conversation.json
API 地址: http://localhost:8000
用户名: admin
用户 ID: default_user
批次大小: 10
问题间延迟: 2.0 秒
模型: default
限制: 10
输出文件: scripts/replay_results.json

加载数据文件...
  - 总记录数: 441
  - 限制回放: 10 条

获取认证 token...
✅ 认证成功

✅ 创建对话成功: conv_123456

开始回放 10 个问答对...
批次大小: 10
问题间延迟: 2.0 秒
模型: default
============================================================

[1/10] 发送问题: 帮我查下 deepseek 最新进展...
  ✅ 成功 (响应时间: 2345ms, 工具调用: 1次)

[2/10] 发送问题: agent skill 与 mcp 有什么区别...
  ✅ 成功 (响应时间: 1892ms, 工具调用: 0次)

...

============================================================
回放完成统计
============================================================
总问题数: 10
成功回放: 10
回放失败: 0
成功率: 100.0%
总耗时: 45.2 秒
平均每分钟: 13.3 个问题
平均响应时间: 2156 ms
工具调用总数: 5

✅ 全部问题回放成功
```

### 输出文件

**位置**: `scripts/replay_results.json`

**内容**:
```json
{
  "timestamp": "2026-06-18T15:30:00",
  "stats": {
    "total": 10,
    "success": 10,
    "failed": 0,
    "timeout": 0,
    "total_response_time_ms": 21560,
    "avg_response_time_ms": 2156,
    "tool_calls_total": 5,
    "elapsed_time": 45.2,
    "questions_per_minute": 13.3
  },
  "results": [
    {
      "success": true,
      "question": "帮我查下 deepseek 最新进展",
      "answer": "根据最新搜索结果...",
      "response_time_ms": 2345,
      "tool_calls_count": 1,
      "tool_names": ["tavily_web_search"],
      "error": null
    },
    ...
  ]
}
```

---

## 🔧 高级用法

### 1. 自定义 API 地址

```bash
# 测试远程服务器
python scripts/replay_qa_pairs.py \
  --input scripts/first_qa_per_conversation.json \
  --api-base http://134.175.182.235:8000 \
  --limit 10
```

### 2. 使用特定模型

```bash
# 使用 DeepSeek 模型
python scripts/replay_qa_pairs.py \
  --input scripts/first_qa_per_conversation.json \
  --model deepseek/deepseek-v4-flash \
  --limit 10

# 使用 Qwen 模型
python scripts/replay_qa_pairs.py \
  --input scripts/first_qa_per_conversation.json \
  --model dashscope/qwen3.7-plus \
  --limit 10
```

### 3. 控制并发速度

```bash
# 快速回放（低延迟）
python scripts/replay_qa_pairs.py \
  --input scripts/first_qa_per_conversation.json \
  --delay 0.5 \
  --limit 50

# 慢速回放（高延迟，避免限流）
python scripts/replay_qa_pairs.py \
  --input scripts/first_qa_per_conversation.json \
  --delay 5.0 \
  --limit 50
```

### 4. 保存结果到指定文件

```bash
python scripts/replay_qa_pairs.py \
  --input scripts/first_qa_per_conversation.json \
  --output scripts/replay_test_20260618.json \
  --limit 100
```

---

## 📊 性能指标

### 关键指标

1. **成功率**: 成功回放的问题比例
2. **平均响应时间**: 从发送到接收响应的平均时间
3. **工具调用次数**: 使用的工具总数
4. **每分钟问题数**: 系统吞吐量

### 性能基准

| 指标 | 优秀 | 良好 | 需优化 |
|------|------|------|--------|
| 成功率 | > 99% | 95-99% | < 95% |
| 平均响应时间 | < 2秒 | 2-5秒 | > 5秒 |
| 每分钟问题数 | > 30 | 10-30 | < 10 |

---

## ⚠️ 注意事项

### 1. API 限流

- 避免过快发送请求
- 建议延迟 >= 1 秒
- 生产环境建议延迟 >= 2 秒

### 2. 超时设置

- 默认超时: 120 秒
- 复杂问题可能需要更长时间
- 可以在代码中调整超时时间

### 3. 认证问题

- 确保用户名密码正确
- 检查用户权限
- 确认 token 有效期

### 4. 数据备份

- 回放会创建新的对话记录
- 建议在测试环境运行
- 生产环境运行前备份数据

---

## 🐛 故障排除

### 问题 1: 认证失败

```bash
# 检查 API 是否可访问
curl http://localhost:8000/

# 检查用户名密码
python scripts/replay_qa_pairs.py \
  --input scripts/first_qa_per_conversation.json \
  --username admin \
  --password admin123 \
  --limit 1
```

### 问题 2: 请求超时

```bash
# 增加延迟时间
python scripts/replay_qa_pairs.py \
  --input scripts/first_qa_per_conversation.json \
  --delay 5.0 \
  --limit 10
```

### 问题 3: 连接被拒绝

```bash
# 检查后端服务是否运行
curl http://localhost:8000/health

# 如果未运行，启动服务
cd /Users/apple/Desktop/code/chat-agent/backend
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

---

## 📚 相关文档

- [实施计划](docs/langfuse_import_plan.md)
- [阶段 1 报告](docs/langfuse_stage1_report.md)
- [导入脚本](scripts/import_to_langfuse.py)
- [评分同步](scripts/sync_scores_to_langfuse.py)

---

## ✅ 验收标准

- [ ] 成功回放首次问答数据
- [ ] 成功回放完整问答数据
- [ ] 响应时间记录正确
- [ ] 工具调用信息完整
- [ ] 结果文件生成正确
- [ ] 统计信息准确
