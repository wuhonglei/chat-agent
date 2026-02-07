"""Embedding 服务：封装文本向量化（用于用户消息语义检索等）"""

from typing import TypeVar

from langchain_community.embeddings import DashScopeEmbeddings

from app.core.config import settings
from app.utils.logger import logger

T = TypeVar("T")


class EmbeddingService:
    """基于 DashScope 的 Embedding 服务，用于单条文本向量化。"""

    def __init__(self) -> None:
        cfg = settings.embedding_model
        self._embeddings = DashScopeEmbeddings(
            model=cfg.model_name,
            dashscope_api_key=cfg.api_key,
        )
        self._model_name = cfg.model_name

    @property
    def model_name(self) -> str:
        """当前使用的 Embedding 模型名称。"""
        return self._model_name

    async def aembed_query(self, text: str) -> list[float]:
        """
        对单条文本进行向量化（异步，在线程池中执行）。

        Args:
            text: 待向量化的文本（会先 strip）。

        Returns:
            向量列表；若文本为空或调用失败，返回空列表并打日志。
        """
        text = (text or "").strip()
        if not text:
            logger.debug("Embedding skipped: empty text")
            return []
        try:
            return await self._embeddings.aembed_query(text)
        except Exception as e:
            logger.warning("Embedding failed", text_length=len(text), error=e)
            return []

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        """
        对多条文本进行向量化（异步，在线程池中执行）。

        Args:
            texts: 待向量化的文本列表。

        Returns:
            向量列表列表；若文本为空或调用失败，返回空列表并打日志。
        """
        texts = [text.strip() for text in texts if text.strip()]
        if not texts:
            logger.debug("Embedding skipped: empty texts")
            return []
        try:
            return await self._embeddings.aembed_documents(texts)
        except Exception as e:
            logger.warning("Embedding failed", texts_count=len(texts), error=e)
            return []
