"""附件文本 token 计数（与 embedding 索引使用同一 tokenizer）。"""

from __future__ import annotations

from app.core.config import settings
from app.services.base_service.embedding_service import EmbeddingService
from app.utils.token import TokenCalculator


def count_attachment_token_size(text: str) -> int:
    """按 embedding 模型 tokenizer 计算文本 token 数。"""
    normalized = text.strip()
    if not normalized:
        return 0
    embedding_service = EmbeddingService(settings.embedding_model)
    calculator = TokenCalculator(
        embedding_service.model_name, settings.embedding_model.context_limit
    )
    return calculator.count_tokens(normalized)
