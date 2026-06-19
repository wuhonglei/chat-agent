# Langfuse 问答数据记录实施计划

## 📋 项目概述

**目标**: 将历史问答数据的延迟、工具调用等指标记录到 Langfuse，用于可观测性分析和性能优化。

**数据源**:
- `scripts/first_qa_per_conversation.json` (441 条首次问答)
- `scripts/live_qa_data_final_v3.json` (879 条问答对)

**目标平台**: Langfuse (自托管: https://langfuse.wuhonglei.cn)

---

## 🎯 实施目标

1. **延迟指标**: 记录用户问题到助手回答的响应时间
2. **工具调用指标**: 记录工具调用次数、工具名称、MCP Server 信息
3. **对话元数据**: 记录对话 ID、标题、用户 ID 等上下文信息
4. **质量指标**: 记录消息状态 (done/stopped/failed)

---

## 📊 数据结构设计

### 1. Trace 结构
```json
{
  "id": "trace_<conversation_id>",
  "name": "chat_conversation",
  "sessionId": "<conversation_id>",
  "userId": "<user_id>",
  "input": {
    "question": "<user_question>",
    "question_length": <length>
  },
  "output": {
    "answer": "<assistant_answer_preview>",
    "answer_length": <length>
  },
  "metadata": {
    "conversation_title": "<title>",
    "tool_calls_count": <count>,
    "tool_names": ["<tool1>", "<tool2>"],
    "server_names": ["<server1>", "<server2>"],
    "source": "historical_data"
  },
  "tags": ["historical", "<interaction_pattern>"]
}
```

### 2. Span 结构 (延迟指标)
```json
{
  "id": "span_<message_id>",
  "traceId": "trace_<conversation_id>",
  "name": "response_latency",
  "startTime": "<user_created_at>",
  "endTime": "<assistant_created_at>",
  "input": {
    "question": "<user_question>"
  },
  "output": {
    "answer_preview": "<first_200_chars>"
  },
  "metadata": {
    "response_time_ms": <ms>,
    "tool_calls_count": <count>
  }
}
```

### 3. Generation 结构 (工具调用)
```json
{
  "id": "gen_<message_id>",
  "traceId": "trace_<conversation_id>",
  "name": "tool_execution",
  "model": "unknown",
  "input": {
    "tool_names": ["<tool1>", "<tool2>"],
    "server_names": ["<server1>", "<server2>"]
  },
  "output": {
    "tool_calls_count": <count>,
    "interaction_pattern": "<pattern>"
  },
  "usage": {
    "inputTokens": 0,
    "outputTokens": 0,
    "totalTokens": 0
  },
  "metadata": {
    "tool_calls": [
      {
        "name": "<tool_name>",
        "server_name": "<server_name>"
      }
    ]
  }
}
```

### 4. Score 结构 (质量指标)
```json
{
  "traceId": "trace_<conversation_id>",
  "name": "message_status",
  "value": 1.0,
  "source": "API",
  "comment": {
    "message_id": "<message_id>",
    "status": "done",
    "updated_at": "<timestamp>"
  }
}
```

---

## 🛠️ 实施步骤

### 阶段 1: 准备工作 (1-2 天)

#### 1.1 环境配置
- [ ] 确认 Langfuse 连接配置 (public_key, secret_key, host)
- [ ] 验证数据库连接配置
- [ ] 测试 Langfuse API 连通性

#### 1.2 数据验证
- [ ] 验证 `first_qa_per_conversation.json` 数据完整性
- [ ] 验证 `live_qa_data_final_v3.json` 数据完整性
- [ ] 检查数据质量 (缺失值、异常值)

#### 1.3 工具准备
- [ ] 创建数据导入脚本模板
- [ ] 准备错误处理和日志记录
- [ ] 创建数据验证脚本

---

### 阶段 2: 核心功能开发 (2-3 天)

#### 2.1 创建基础导入脚本
**文件**: `scripts/import_to_langfuse.py`

**功能**:
- 读取 JSON 数据文件
- 创建 Trace 和 Span
- 记录延迟指标
- 处理错误和重试

**关键代码**:
```python
def create_trace_for_conversation(qa_data: dict) -> str:
    """为对话创建 Trace"""
    trace_id = f"trace_{qa_data['conversation_id']}"

    # 创建 Trace
    langfuse.trace(
        id=trace_id,
        name="chat_conversation",
        session_id=qa_data['conversation_id'],
        user_id=qa_data['user_id'],
        input={"question": qa_data['user_question']},
        output={"answer": qa_data['assistant_answer'][:200]},
        metadata={
            "conversation_title": qa_data['conversation_title'],
            "tool_calls_count": qa_data['tool_calls_count'],
            "tool_names": qa_data['tool_names'],
            "server_names": qa_data['server_names'],
        },
        tags=["historical", qa_data.get('interaction_pattern', 'unknown')]
    )

    return trace_id


def create_latency_span(trace_id: str, qa_data: dict) -> None:
    """创建延迟 Span"""
    if not qa_data.get('response_time_ms'):
        return

    langfuse.span(
        trace_id=trace_id,
        name="response_latency",
        start_time=qa_data['user_created_at'],
        end_time=qa_data['assistant_created_at'],
        input={"question": qa_data['user_question']},
        output={"answer_preview": qa_data['assistant_answer'][:200]},
        metadata={
            "response_time_ms": qa_data['response_time_ms'],
            "tool_calls_count": qa_data['tool_calls_count'],
        }
    )


def create_tool_generation(trace_id: str, qa_data: dict) -> None:
    """创建工具调用 Generation"""
    if qa_data['tool_calls_count'] == 0:
        return

    langfuse.generation(
        trace_id=trace_id,
        name="tool_execution",
        model="unknown",
        input={
            "tool_names": qa_data['tool_names'],
            "server_names": qa_data['server_names'],
        },
        output={
            "tool_calls_count": qa_data['tool_calls_count'],
        },
        usage={
            "inputTokens": 0,
            "outputTokens": 0,
            "totalTokens": 0,
        },
        metadata={
            "tool_calls": qa_data['tool_calls'],
        }
    )
```

#### 2.2 创建质量评分脚本
**文件**: `scripts/sync_scores_to_langfuse.py`

**功能**:
- 同步消息状态到 Langfuse Score
- 扩展现有的 `sync_status_to_langfuse.py`
- 支持批量处理

#### 2.3 创建数据验证脚本
**文件**: `scripts/validate_langfuse_data.py`

**功能**:
- 验证导入的数据是否正确
- 检查 Trace 和 Span 的完整性
- 生成验证报告

---

### 阶段 3: 高级功能 (2-3 天)

#### 3.1 批量导入优化
- [ ] 实现分批导入 (每批 50-100 条)
- [ ] 添加进度条和统计信息
- [ ] 实现断点续传功能
- [ ] 添加并发控制 (避免 API 限流)

#### 3.2 数据增强
- [ ] 计算交互模式分类 (simple_chat, single_tool, multi_tool)
- [ ] 添加工具调用详情 (输入参数、执行结果)
- [ ] 计算额外指标 (问题复杂度、回答质量)

#### 3.3 错误处理和监控
- [ ] 实现重试机制 (指数退避)
- [ ] 添加详细的错误日志
- [ ] 创建导入状态报告
- [ ] 实现数据一致性检查

---

### 阶段 4: 测试和部署 (1-2 天)

#### 4.1 单元测试
- [ ] 测试数据解析函数
- [ ] 测试 Trace/Span 创建逻辑
- [ ] 测试错误处理流程

#### 4.2 集成测试
- [ ] 测试 Langfuse API 调用
- [ ] 测试批量导入流程
- [ ] 测试数据一致性

#### 4.3 部署和验证
- [ ] 在测试环境验证
- [ ] 导入首批数据 (10-20 条)
- [ ] 验证 Langfuse 仪表盘显示
- [ ] 导入完整数据集

---

## 📁 文件结构

```
scripts/
├── import_to_langfuse.py          # 主导入脚本
├── sync_scores_to_langfuse.py     # 评分同步脚本
├── validate_langfuse_data.py      # 数据验证脚本
├── langfuse_batch_import.py       # 批量导入工具
├── first_qa_per_conversation.json # 首次问答数据
├── live_qa_data_final_v3.json     # 完整问答数据
└── langfuse_import_log.json       # 导入日志
```

---

## 🔧 技术栈

- **Python 3.11+**
- **Langfuse SDK**: `langfuse` Python 包
- **数据库**: PostgreSQL (psycopg2)
- **数据格式**: JSON
- **日志**: Python logging
- **进度条**: tqdm (可选)

---

## 📈 预期成果

### 1. Langfuse 仪表盘指标
- **延迟分布**: 响应时间直方图
- **工具调用统计**: 各工具使用频率
- **对话质量**: 消息状态分布
- **用户行为**: 首次问答模式分析

### 2. 可观测性指标
- **P50/P90/P95 延迟**: 响应时间百分位
- **工具调用成功率**: 工具执行统计
- **对话完成率**: 消息状态统计
- **用户满意度**: 基于反馈评分

### 3. 数据洞察
- **高频工具**: 识别最常用的工具
- **性能瓶颈**: 识别慢响应对话
- **用户模式**: 识别常见问题类型
- **优化机会**: 识别可优化的工具调用

---

## ⚠️ 风险和缓解措施

### 风险 1: API 限流
**缓解措施**:
- 实现请求间隔控制
- 使用批量 API (如果支持)
- 实现重试机制

### 风险 2: 数据不一致
**缓解措施**:
- 使用确定性 Trace ID
- 实现数据验证检查
- 记录导入日志

### 风险 3: 内存溢出
**缓解措施**:
- 分批处理数据
- 使用流式读取
- 监控内存使用

### 风险 4: 网络中断
**缓解措施**:
- 实现断点续传
- 保存导入进度
- 自动重试机制

---

## 📅 时间线

| 阶段 | 任务 | 时间 | 产出 |
|------|------|------|------|
| 1 | 准备工作 | 1-2 天 | 环境配置、数据验证 |
| 2 | 核心功能 | 2-3 天 | 导入脚本、评分同步 |
| 3 | 高级功能 | 2-3 天 | 批量优化、数据增强 |
| 4 | 测试部署 | 1-2 天 | 测试验证、生产部署 |
| **总计** | | **6-10 天** | 完整的 Langfuse 集成 |

---

## 🚀 快速开始

### 1. 安装依赖
```bash
pip install langfuse psycopg2-binary tqdm
```

### 2. 配置环境变量
```bash
export LANGFUSE_PUBLIC_KEY="pk-lf-..."
export LANGFUSE_SECRET_KEY="sk-lf-..."
export LANGFUSE_HOST="https://langfuse.wuhonglei.cn"
```

### 3. 运行导入脚本
```bash
# 导入首次问答数据
python scripts/import_to_langfuse.py --input scripts/first_qa_per_conversation.json --batch-size 50

# 导入完整问答数据
python scripts/import_to_langfuse.py --input scripts/live_qa_data_final_v3.json --batch-size 100

# 验证导入结果
python scripts/validate_langfuse_data.py --sample-size 20
```

---

## 📚 参考资料

- [Langfuse Python SDK 文档](https://langfuse.com/docs/sdk/python)
- [Langfuse API 参考](https://langfuse.com/docs/api)
- [现有 sync_status_to_langfuse.py](backend/scripts/sync_status_to_langfuse.py)
- [Langfuse 可观测性最佳实践](https://langfuse.com/docs/analytics)

---

## ✅ 验收标准

1. **功能完整性**
   - [ ] 成功导入 441 条首次问答数据
   - [ ] 成功导入 879 条完整问答数据
   - [ ] 延迟指标正确记录
   - [ ] 工具调用信息完整

2. **数据质量**
   - [ ] Trace ID 唯一且确定性
   - [ ] 时间戳格式正确
   - [ ] 元数据完整准确
   - [ ] 无重复数据

3. **性能要求**
   - [ ] 批量导入速度 > 10 条/秒
   - [ ] 内存使用 < 500MB
   - [ ] 错误率 < 1%

4. **可观测性**
   - [ ] Langfuse 仪表盘正确显示
   - [ ] 指标计算准确
   - [ ] 数据可查询和分析
