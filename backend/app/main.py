"""Main FastAPI application"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.api import chat, health, conversation, message
from app.core.config import settings
from app.core.db import create_db_and_tables
from app.mcp.mcp_client import get_mcp_manager
from app.models import User, Conversation, Message  # 导入模型以注册表到 metadata


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")

    # 创建数据库表（如果权限允许）
    # 如果权限不足，应用会继续运行但需要手动创建表
    create_db_and_tables()

    app.state.mcp_manager = await get_mcp_manager()

    logger.info("Application startup complete")

    yield
    # 清理 MCP Manager 资源
    app.state.mcp_manager.cleanup()
    logger.info("Shutting down application")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
app.include_router(message.router, prefix="/api/message", tags=["message"])
app.include_router(conversation.router,
                   prefix="/api/conversation", tags=["conversation"])
app.include_router(health.router, prefix="/api/health", tags=["health"])


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
    }
