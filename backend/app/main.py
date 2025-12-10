"""Main FastAPI application"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import auth, chat, health, conversation, message, user, file
from app.core.config import settings
from app.core.db import create_db_and_tables
from app.mcp.mcp_client import get_mcp_manager
from app.models import UserDb, ConversationDb, MessageDb  # 导入模型以注册表到 metadata
from app.jwt.jwt_manager import initialize_jwt_manager
from app.middleware import LoggingMiddleware
from app.utils.logger import logger, setup_logger

# 配置日志系统
setup_logger(debug=settings.app.debug)


@asynccontextmanager
async def lifespan(app: FastAPI):
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

# Include routers
app.include_router(user.router, prefix="/api/user", tags=["user"])
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
app.include_router(message.router, prefix="/api/message", tags=["message"])
app.include_router(conversation.router,
                   prefix="/api/conversation", tags=["conversation"])
app.include_router(health.router, prefix="/api/health", tags=["health"])
app.include_router(file.router, prefix="/api/file", tags=["file"])


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": settings.app.name,
        "version": settings.app.version,
        "status": "running",
    }
