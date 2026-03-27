# 日志使用指南

本文档说明如何在项目中使用结构化日志系统。

## 核心特性

1. **结构化日志**：所有日志都包含上下文信息（request_id, user_id, client_ip等）
2. **请求追踪**：每个请求都有唯一的 request_id，便于追踪
3. **上下文绑定**：自动绑定 user_id 到日志上下文
4. **敏感信息保护**：不记录敏感数据（密码、token、用户消息内容等）

## 基本使用

### 导入日志工具

```python
from app.utils.logger import logger
```

### 记录不同级别的日志

```python
# INFO 级别 - 记录关键操作
logger.info("User logged in", user_id=user_id)

# WARNING 级别 - 记录警告信息
logger.warning("Rate limit approaching", user_id=user_id, remaining=10)

# ERROR 级别 - 记录错误
logger.error("Failed to save message", error=exc, message_id=message_id)

# DEBUG 级别 - 记录调试信息（仅在 debug 模式下）
logger.debug("Processing request", step="validation")

# EXCEPTION 级别 - 记录异常（包含完整堆栈）
logger.exception("Unexpected error occurred", operation="file_upload")
```

## 上下文信息

日志系统会自动包含以下上下文信息：

- `request_id`: 每个请求的唯一标识（由中间件自动生成）
- `user_id`: 当前用户ID（在认证成功后自动绑定）
- `client_ip`: 客户端IP地址（由中间件自动绑定）

### 手动添加额外上下文

```python
logger.info(
    "File uploaded",
    file_id=file_id,
    file_size=file_size,
    file_type=file_type,
)
```

输出示例：
```
2025-01-20 10:30:15.123 | INFO     | app.api.file:upload_file:45 | File uploaded | request_id=abc-123 | user_id=user-456 | file_id=file-789 | file_size=1024 | file_type=image/png
```

## 最佳实践

### ✅ 应该记录的信息

1. **操作摘要**：操作类型、结果、资源ID
```python
logger.info(
    "Message created",
    message_id=message_id,
    conversation_id=conversation_id,
    message_type="user",
)
```

2. **性能指标**：处理时间、数据大小
```python
logger.info(
    "Request completed",
    process_time="0.123s",
    response_size=1024,
)
```

3. **错误信息**：错误类型、错误位置（不含敏感数据）
```python
logger.error(
    "Database connection failed",
    error=exc,
    operation="save_message",
)
```

### ❌ 不应该记录的信息

1. **用户隐私数据**：
```python
# ❌ 错误
logger.info(f"User data: {user}")  # 包含手机号、邮箱等

# ✅ 正确
logger.info("User created", user_id=user.id)
```

2. **认证信息**：
```python
# ❌ 错误
logger.info(f"Token: {token}")
logger.info(f"Password: {password}")

# ✅ 正确
logger.info("User authenticated", user_id=user_id)
```

3. **用户消息内容**：
```python
# ❌ 错误
logger.info(f"User message: {chat_request.content}")

# ✅ 正确
logger.info(
    "Chat request received",
    conversation_id=conversation_id,
    message_length=len(chat_request.content),
)
```

4. **完整的请求/响应体**：
```python
# ❌ 错误
logger.info(f"Request body: {request.json()}")

# ✅ 正确
logger.info(
    "Request received",
    method=request.method,
    path=request.url.path,
)
```

## 在 API 路由中使用

### 示例：聊天接口

```python
from app.utils.logger import logger

@router.post("/stream")
async def chat_stream(
    request: Request,
    chat_request: ChatRequest,
    _auth: None = Depends(require_auth),
):
    # 记录请求（不包含敏感内容）
    logger.info(
        "Chat stream request received",
        conversation_id=chat_request.conversation_id,
        message_length=len(chat_request.content) if chat_request.content else 0,
    )

    try:
        # 业务逻辑
        ...
    except Exception as exc:
        logger.error(
            "Failed to process chat request",
            error=exc,
            conversation_id=chat_request.conversation_id,
        )
        raise
```

## 在服务层中使用

```python
from app.utils.logger import logger

class MessageService:
    def create_message(self, message_id: str, content: str):
        try:
            # 创建消息
            logger.info(
                "Creating message",
                message_id=message_id,
                content_length=len(content),  # 只记录长度，不记录内容
            )
            # ...
        except Exception as e:
            logger.error(
                "Failed to create message",
                error=e,
                message_id=message_id,
            )
            raise
```

## 请求追踪

每个请求都会自动生成 `request_id`，并在响应头中返回：

```bash
curl -i http://localhost:8000/api/chat/stream
# 响应头中包含：
# X-Request-ID: abc-123-def-456
```

可以通过 `request_id` 在日志中追踪整个请求的处理流程。

## 日志格式

日志格式统一为：
```
{time} | {level} | {module}:{function}:{line} | {message} | {context}
```

示例：
```
2025-01-20 10:30:15.123 | INFO     | app.api.chat:chat_stream:30 | Chat stream request received | request_id=abc-123 | user_id=user-456 | conversation_id=conv-789 | message_length=42
```

## 配置

日志级别由 `settings.app.debug` 控制：
- `debug=True`: 输出 DEBUG 及以上级别
- `debug=False`: 输出 INFO 及以上级别（生产环境推荐）

## 迁移指南

### 从旧日志迁移

**旧代码：**
```python
from loguru import logger
logger.info(f"User {user_id} created message {message_id}")
logger.error(f"Failed: {exc}")
```

**新代码：**
```python
from app.utils.logger import logger
logger.info("Message created", user_id=user_id, message_id=message_id)
logger.error("Failed to create message", error=exc, user_id=user_id)
```

### 优势

1. **自动上下文**：无需手动添加 request_id、user_id
2. **结构化**：便于日志收集系统解析
3. **一致性**：统一的日志格式
4. **安全性**：避免意外记录敏感信息
