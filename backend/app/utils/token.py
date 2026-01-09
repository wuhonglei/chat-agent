"""Token 计算和消息截断工具"""
import json
import time

from openai import BaseModel
import tiktoken
from requests.exceptions import SSLError, RequestException
from app.schemas.llm import AssistantToolCallMessage, ToolCallMessage, ToolCallResultMessage
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

        如果网络请求失败（如 SSL 错误），会重试并尝试使用本地缓存

        Returns:
            tiktoken.Encoding 对象
        """
        max_retries = 3
        retry_delay = 1  # 秒

        for attempt in range(max_retries):
            try:
                # 尝试获取编码器
                encoding = tiktoken.get_encoding(self.DEFAULT_ENCODING_NAME)
                return encoding
            except Exception as e:
                # 检查是否是网络相关的错误
                is_network_error = (
                    isinstance(e, (SSLError, RequestException)) or
                    "SSL" in str(type(e).__name__) or
                    "Connection" in str(type(e).__name__) or
                    "network" in str(e).lower() or
                    "openaipublic.blob.core.windows.net" in str(e)
                )

                if not is_network_error:
                    # 如果不是网络错误，直接抛出
                    raise

                # 网络错误（SSL 错误、连接错误等）
                if attempt < max_retries - 1:
                    logger.warning(
                        f"获取 tiktoken 编码失败 (尝试 {attempt + 1}/{max_retries}): {e}，"
                        f"{retry_delay} 秒后重试"
                    )
                    time.sleep(retry_delay)
                    retry_delay *= 2  # 指数退避
                else:
                    # 最后一次尝试失败，尝试使用本地缓存或降级方案
                    logger.error(
                        f"获取 tiktoken 编码失败，尝试使用本地缓存或降级方案: {e}"
                    )
                    # 尝试使用 encoding_for_model，它可能会使用不同的下载方式
                    try:
                        encoding = tiktoken.encoding_for_model(self.model)
                        logger.info("使用 encoding_for_model 成功获取编码")
                        return encoding
                    except Exception as fallback_error:
                        logger.error(
                            f"降级方案也失败: {fallback_error}，"
                            "将使用简化的字符计数作为近似值"
                        )
                        # 如果所有方法都失败，返回一个简化的编码器
                        # 注意：这只是一个降级方案，精度会降低
                        raise RuntimeError(
                            "无法初始化 tiktoken 编码器，可能是网络问题。"
                            "请检查网络连接或代理设置。"
                        ) from e
            except KeyError:
                # 如果编码器不存在，使用默认的
                try:
                    encoding = tiktoken.encoding_for_model(self.model)
                    return encoding
                except Exception as e:
                    logger.error(f"无法获取模型编码: {e}")
                    raise

        # 理论上不会到达这里
        raise RuntimeError("无法获取 tiktoken 编码器")

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
