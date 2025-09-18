# 检索系统架构文档

## 概述

本项目实现了一个可扩展的多源检索系统，支持从多个数据源获取信息并进行智能整合。目前支持向量数据库检索和联网搜索，后续可轻松扩展支持 Confluence、Google Docs 等企业级数据源。

## 架构设计

### 核心组件

```
检索系统架构:
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Chat Service  │────│ Retrieval Mgr   │────│   LLM Service   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │
                    ┌───────────┴───────────┐
                    │                       │
            ┌───────▼────────┐     ┌───────▼────────┐
            │ Vector Store   │     │  External      │
            │ Retriever      │     │  Retrievers    │
            └────────────────┘     └────────────────┘
                                          │
                    ┌─────────────────────┼─────────────────────┐
                    │                     │                     │
            ┌───────▼────────┐   ┌───────▼────────┐   ┌───────▼────────┐
            │ Web Search     │   │ Confluence     │   │ Google Docs    │
            │ (Tavily)       │   │ Retriever      │   │ Retriever      │
            └────────────────┘   └────────────────┘   └────────────────┘
```

### 主要特性

1. **可扩展架构**: 基于工厂模式和接口设计，易于添加新的检索源
2. **并行检索**: 支持同时从多个源检索数据
3. **智能重排序**: 结合多源结果进行统一排序
4. **健康监控**: 实时监控各检索源状态
5. **配置热重载**: 支持运行时重新配置检索器

## 使用方法

### 1. 环境配置

复制 `.env.example` 为 `.env` 并配置 Tavily API Key：

```bash
# Web Search
TAVILY_API_KEY=your_tavily_api_key
```

### 2. API 使用示例

#### 聊天接口（支持多源检索）

```bash
# 仅使用知识库
curl -X POST "http://localhost:8000/api/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "什么是人工智能？",
    "source_config": {
      "knowledge_base": true,
      "web_search": false
    }
  }'

# 仅使用联网搜索
curl -X POST "http://localhost:8000/api/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "2024年最新的AI发展趋势",
    "source_config": {
      "knowledge_base": false,
      "web_search": true
    }
  }'

# 同时使用知识库和联网搜索
curl -X POST "http://localhost:8000/api/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "结合内部文档和最新资讯，分析AI在我们公司的应用前景",
    "source_config": {
      "knowledge_base": true,
      "web_search": true
    }
  }'

# 带会话历史和思考模式
curl -X POST "http://localhost:8000/api/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "基于之前的讨论，深入分析这个问题",
    "session_id": "uuid-string",
    "think_mode": true,
    "history": [
      {
        "role": "user",
        "content": "什么是深度学习？"
      },
      {
        "role": "assistant",
        "content": "深度学习是机器学习的一个分支..."
      }
    ],
    "source_config": {
      "knowledge_base": true,
      "web_search": true
    }
  }'
```

#### 流式聊天接口

```bash
# 流式响应
curl -X POST "http://localhost:8000/api/chat/stream" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "详细解释深度学习的原理",
    "session_id": "uuid-string",
    "source_config": {
      "knowledge_base": true,
      "web_search": false
    }
  }'
```

#### 直接检索接口

```bash
# 多源检索
curl -X POST "http://localhost:8000/api/retrieval/search" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "人工智能发展趋势",
    "sources": ["vector_store", "web_search"],
    "max_results": 5,
    "min_score": 0.7
  }'
```

#### 健康检查

```bash
# 检查所有检索源状态
curl "http://localhost:8000/api/retrieval/health"

# 查看可用检索源
curl "http://localhost:8000/api/retrieval/sources"
```

### 3. 响应格式

#### 聊天响应

```json
{
  "message": "基于搜索结果的AI回答...",
  "sources": [
    {
      "content": "检索到的内容摘要...",
      "title": "文档标题或网页标题",
      "url": "https://example.com/article",
      "source": "web_search",
      "score": 0.95
    }
  ],
  "session_id": "uuid-string",
  "timestamp": "2024-01-01T12:00:00Z"
}
```

#### 检索响应

```json
{
  "results": [
    {
      "content": "检索内容",
      "title": "标题",
      "url": "链接（如果有）",
      "source": "web_search",
      "score": 0.95,
      "metadata": {},
      "retrieved_at": "2024-01-01T12:00:00Z"
    }
  ],
  "query": "搜索查询",
  "total_results": 5,
  "sources_used": ["vector_store", "web_search"],
  "processing_time_ms": 1250.5,
  "timestamp": "2024-01-01T12:00:00Z"
}
```

## 扩展指南

### 添加新的检索源

1. **创建检索器实现**

```python
# app/services/retrievers/confluence_retriever.py
from app.services.retrievers.base import BaseRetriever
from app.models.retrieval import RetrievalRequest, RetrievalResult, RetrievalSource

class ConfluenceRetriever(BaseRetriever):
    def __init__(self, api_config):
        super().__init__("Confluence")
        self.api_config = api_config

    async def retrieve(self, request: RetrievalRequest) -> List[RetrievalResult]:
        # 实现 Confluence 检索逻辑
        pass

    async def health_check(self) -> bool:
        # 实现健康检查
        pass
```

2. **注册到工厂**

```python
# app/services/retrievers/factory.py
def _init_retrievers(self):
    # 现有检索器...

    # 新增 Confluence 检索器
    if hasattr(settings, "CONFLUENCE_API_TOKEN") and settings.CONFLUENCE_API_TOKEN:
        self._retrievers[RetrievalSource.CONFLUENCE] = ConfluenceRetriever(
            api_config={
                "url": settings.CONFLUENCE_URL,
                "token": settings.CONFLUENCE_API_TOKEN
            }
        )
```

3. **更新枚举类型**

```python
# app/models/retrieval.py
class RetrievalSource(str, Enum):
    VECTOR_STORE = "vector_store"
    WEB_SEARCH = "web_search"
    CONFLUENCE = "confluence"  # 新增
```

## 技术栈

- **FastAPI**: REST API 框架
- **LangChain**: 检索增强生成框架
- **Tavily**: 联网搜索服务
- **ChromaDB**: 向量数据库
- **DeepSeek**: 大语言模型
- **Pydantic**: 数据验证和序列化

## 性能优化

1. **并行检索**: 多个检索源同时执行
2. **结果缓存**: Redis 缓存常用查询结果
3. **连接池**: 复用 HTTP 连接
4. **超时控制**: 防止慢查询影响整体性能
5. **重排序优化**: 智能合并和排序多源结果

## 监控和运维

- **健康检查**: `/api/retrieval/health`
- **性能指标**: 检索时间、成功率等
- **日志记录**: 详细的检索日志
- **配置重载**: `/api/retrieval/reload`

## 后续规划

1. ✅ **联网搜索**: Tavily Search 集成
2. 🔄 **Confluence**: 企业知识库集成
3. 🔄 **Google Docs**: 在线文档集成
4. 🔄 **PDF 检索**: 本地文件智能检索
5. 🔄 **缓存优化**: 智能缓存策略
6. 🔄 **结果去重**: 跨源结果去重算法