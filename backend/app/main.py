"""Main FastAPI application"""

from contextlib import asynccontextmanager
from typing import cast

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.api import chat, documents, health, knowledge_base, retrieval
from app.core.config import settings
from app.core.vector_store import initialize_vector_manager
from app.models.app_state import AppState


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")

    # Initialize vector store
    app.state.vector_manager = await initialize_vector_manager()

    logger.info("Application startup complete")

    yield

    # Cleanup
    state = cast(AppState, app.state)
    if state.vector_manager:
        await state.vector_manager.close()
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
app.include_router(health.router, prefix="/api/health", tags=["health"])
app.include_router(
    documents.router, prefix="/api/documents", tags=["documents"])
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
app.include_router(knowledge_base.router,
                   prefix="/api/knowledge-base", tags=["knowledge-base"])
app.include_router(
    retrieval.router, prefix="/api/retrieval", tags=["retrieval"])


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
    }
