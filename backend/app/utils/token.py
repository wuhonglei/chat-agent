"""Token 计算和消息截断工具"""
import json
from typing import Any

import tiktoken
from app.utils.logger import logger


class TokenCalculator:
    """Token 计算工具类"""

    # 常见模型的上下文限制
    MODEL_LIMITS = {
        "deepseek-chat": 131072,
        "deepseek-reasoner": 131072,
        "gpt-4": 8192,
        "gpt-4-turbo": 128000,
        "gpt-4o": 128000,
        "gpt-3.5-turbo": 16385,
        "claude-3-opus": 200000,
        "claude-3-sonnet": 200000,
        "claude-3-haiku": 200000,
    }

    DEFAULT_LIMIT = 131072  # deepseek 的默认限制
    DEFAULT_ENCODING_NAME = "cl100k_base"

    def __init__(self, model: str):
        """
        初始化 Token 计算器

        Args:
            model: 模型名称
        """
        self.model = model
        self._encoding = None

    @property
    def encoding(self) -> tiktoken.Encoding:
        """
        获取模型的编码器（延迟加载）

        Returns:
            tiktoken.Encoding 对象
        """
        if self._encoding is None:
            self._encoding = self._get_token_encoding()
        return self._encoding

    def get_max_context_tokens(self) -> int:
        """
        获取模型的最大上下文 token 数量

        Returns:
            最大上下文 token 数量
        """
        # 检查模型名称是否包含已知的模型标识
        for model_key, limit in self.MODEL_LIMITS.items():
            if model_key in self.model.lower():
                return limit

        # 默认值：131072（deepseek 的默认限制）
        return self.DEFAULT_LIMIT

    def _get_token_encoding(self) -> tiktoken.Encoding:
        """
        根据模型选择编码器，默认使用 cl100k_base（GPT-4 和大多数现代模型使用）
        对于 deepseek 模型，也使用 cl100k_base

        Returns:
            tiktoken.Encoding 对象
        """
        # 尝试获取编码器
        try:
            encoding = tiktoken.get_encoding(self.DEFAULT_ENCODING_NAME)
        except KeyError:
            # 如果编码器不存在，使用默认的
            encoding = tiktoken.encoding_for_model(self.model)

        return encoding

    def count_tokens(self, text: str) -> int:
        """
        计算文本的 token 数量

        Args:
            text: 要计算的文本

        Returns:
            token 数量
        """
        return len(self.encoding.encode(text or ""))

    @classmethod
    def get_max_context_tokens_for_model(cls, model: str) -> int:
        """
        类方法：获取指定模型的最大上下文 token 数量

        Args:
            model: 模型名称

        Returns:
            最大上下文 token 数量
        """
        calculator = cls(model)
        return calculator.get_max_context_tokens()
