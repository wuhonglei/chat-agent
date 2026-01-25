"""Main FastAPI application"""

import warnings
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError

from app.api import auth, chat, conversation, file, health, message, user
from app.core.config import settings
from app.core.db import create_db_and_tables
from app.core.jwt import initialize_jwt_manager
from app.mcp.mcp_client import get_mcp_manager
from app.middleware import LoggingMiddleware
from app.middleware.exception_handler import (
    general_exception_handler,
    http_exception_handler,
    validation_exception_handler,
)
from app.utils.logger import logger, setup_logger

# 忽略 nacos 库中的 SSL DeprecationWarning
warnings.filterwarnings("ignore", category=DeprecationWarning, module="nacos.*")


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

    # 初始化 MCP Manager
    app.state.mcp_manager = await get_mcp_manager()

    # 初始化 JWT Manager（提前加载密钥文件，避免每次请求时重复读取）
    app.state.jwt_manager = initialize_jwt_manager()

    logger.info("Application startup complete")

    yield
    # 清理 MCP Manager 资源
    app.state.mcp_manager.cleanup()
    logger.info("Application shutting down")


app = FastAPI(
    title=settings.app.name,
    version=settings.app.version,
    lifespan=lifespan,
)

# 添加日志中间件（必须在路由之前添加）
# 执行顺序：中间件 → 路由匹配 → 依赖注入 → 路由处理函数 → 依赖清理 → 中间件继续
app.add_middleware(LoggingMiddleware)

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
app.include_router(message.router, prefix="/api/message", tags=["message"])
app.include_router(
    conversation.router, prefix="/api/conversation", tags=["conversation"]
)
app.include_router(health.router, prefix="/api/health", tags=["health"])
app.include_router(file.router, prefix="/api/file", tags=["file"])


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint"""
    return {
        "name": settings.app.name,
        "version": settings.app.version,
        "status": "running",
    }
