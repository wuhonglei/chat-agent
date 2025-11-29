"""Main FastAPI application"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from loguru import logger

from app.api import auth, chat, health, conversation, message, user, file
from app.core.config import settings
from app.core.db import create_db_and_tables
from app.mcp.mcp_client import get_mcp_manager
from app.models import UserDb, ConversationDb, MessageDb  # 导入模型以注册表到 metadata
from app.jwt.jwt_manager import initialize_jwt_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    logger.info(f"Starting {settings.app.name} v{settings.app.version}")

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
    logger.info("Shutting down application")


app = FastAPI(
    title=settings.app.name,
    version=settings.app.version,
    lifespan=lifespan,
)

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
