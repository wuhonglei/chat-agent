"""Token 计算和消息截断工具"""
import os
import json

from openai import BaseModel
import tiktoken
from app.utils.logger import logger

# 配置代理（替换为你的有效代理地址和端口）
os.environ["HTTP_PROXY"] = "http://127.0.0.1:7890"  # 替换为你的 HTTP 代理
os.environ["HTTPS_PROXY"] = "http://127.0.0.1:7890"  # HTTPS 代理通常与 HTTP 代理一致


class TokenCalculator:
    """Token 计算工具类"""

    # 常见模型的上下文限制
    MODEL_LIMITS = {
        "deepseek-chat": 131072,
        "deepseek-reasoner": 131072,
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
        self.encoding = self._get_encoding(model)

    def _get_encoding(self, model: str) -> tiktoken.Encoding:
        try:
            return tiktoken.encoding_for_model(model)
        except KeyError:
            # 如果模型无法自动映射，使用默认的 encoding
            # 大多数现代模型（包括 Qwen）使用 cl100k_base
            logger.warning(
                f"无法自动映射模型 {model} 到 tokenizer，使用默认 encoding: {self.DEFAULT_ENCODING_NAME}"
            )
            return tiktoken.get_encoding(self.DEFAULT_ENCODING_NAME)

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

    def count_messages_tokens(self, messages: list[dict | BaseModel]) -> int:
        """
        计算消息列表的 token 数量

        注意：这是一个简化的计算方式，实际 API 调用时的 token 数量可能略有不同
        因为需要考虑消息格式、工具定义等额外开销

        Args:
            messages: 消息列表，格式为 [{"role": "system", "content": "..."}, ...]

        Returns:
            token 数量
        """
        total_tokens = 0
        # 每条消息的基础开销（role + 格式标记等），大约 4 tokens
        base_tokens_per_message = 4

        for message in messages:
            total_tokens += base_tokens_per_message
            if isinstance(message, BaseModel):
                message = message.model_dump()

            # 计算 content 的 token
            content = message.get("content", "")
            if content:
                total_tokens += self.count_tokens(content)

            # 计算 reasoning_content 的 token（如果存在）
            reasoning_content = message.get("reasoning_content", "")
            if reasoning_content:
                total_tokens += self.count_tokens(reasoning_content)

            # 计算 tool_calls 的 token（如果存在）
            tool_calls = message.get("tool_calls", [])
            if tool_calls:
                total_tokens += self.count_tokens(json.dumps(tool_calls))

        return total_tokens
