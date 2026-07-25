"""Main FastAPI application"""

import asyncio
import warnings
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator
from pydantic import ValidationError

from app.api import (
    auth,
    avatars,
    chat,
    code,
    conversation,
    file,
    health,
    message,
    models,
    user,
    user_data,
)
from app.core.config import settings
from app.core.db import create_db_and_tables
from app.core.jwt import initialize_jwt_manager
from app.core.observability import init_langfuse, shutdown_langfuse
from app.core.redis import close_redis, init_redis
from app.mcp import get_mcp_manager, register_mcp_reload_target
from app.middleware import LoggingMiddleware
from app.middleware.exception_handler import (
    general_exception_handler,
    http_exception_handler,
    validation_exception_handler,
)
from app.utils.logger import logger, setup_logger

# 忽略 nacos 库中的 SSL DeprecationWarning
warnings.filterwarnings(
    "ignore", category=DeprecationWarning, module=r"(nacos|v2\.nacos).*"
)


# 配置日志系统
setup_logger(debug=settings.app.debug)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager"""
    logger.info(
        "Application starting",
        app_name=settings.app.name,
        version=settings.app.version,
        debug=settings.app.debug,
    )

    # 创建数据库表（如果权限允许）
    # 如果权限不足，应用会继续运行但需要手动创建表
    create_db_and_tables()

    # 初始化 MCP Manager，并注册 Nacos 热更新回调目标
    mcp_manager = await get_mcp_manager()
    app.state.mcp_manager = mcp_manager
    register_mcp_reload_target(asyncio.get_running_loop(), mcp_manager)

    # 初始化 Langfuse 可观测客户端（失败不影响主流程）
    init_langfuse()

    # 初始化 JWT Manager（提前加载密钥文件，避免每次请求时重复读取）
    app.state.jwt_manager = initialize_jwt_manager()

    # 初始化 Redis 连接池
    app.state.redis = await init_redis()

    logger.info("Application startup complete")

    yield
    # 刷新 Langfuse 队列，避免进程退出丢事件
    shutdown_langfuse()
    await close_redis()
    # 清理 MCP Manager 资源
    app.state.mcp_manager.cleanup()
    logger.info("Application shutting down")


app = FastAPI(
    title=settings.app.name,
    version=settings.app.version,
    lifespan=lifespan,
)

# Prometheus 指标暴露（/metrics 端点）
Instrumentator().instrument(app).expose(app)

# 添加日志中间件（必须在路由之前添加）
# 执行顺序：中间件 → 路由匹配 → 依赖注入 → 路由处理函数 → 依赖清理 → 中间件继续
app.add_middleware(LoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors.allow_origins,
    allow_credentials=settings.cors.allow_credentials,
    allow_methods=settings.cors.allow_methods,
    allow_headers=settings.cors.allow_headers,
)

# 注册全局异常处理器（按优先级顺序注册）
# 1. 验证异常处理器（最具体）
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(ValidationError, validation_exception_handler)

# 2. HTTP 异常处理器
app.add_exception_handler(HTTPException, http_exception_handler)

# 3. 通用异常处理器（兜底，必须最后注册）
app.add_exception_handler(Exception, general_exception_handler)

# Include routers
app.include_router(user.router, prefix="/api/user", tags=["user"])
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
app.include_router(models.router, prefix="/api/chat", tags=["chat"])
app.include_router(message.router, prefix="/api/message", tags=["message"])
app.include_router(
    conversation.router, prefix="/api/conversation", tags=["conversation"]
)
app.include_router(health.router, prefix="/api/health", tags=["health"])
app.include_router(file.router, prefix="/api/file", tags=["file"])
app.include_router(avatars.router, prefix="/api/avatars", tags=["avatars"])
app.include_router(code.router, prefix="/api/code", tags=["code"])
app.include_router(
    user_data.router,
    prefix="/api/user_data",
    tags=["user_data"],
)


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint"""
    return {
        "name": settings.app.name,
        "version": settings.app.version,
        "status": "running",
    }
