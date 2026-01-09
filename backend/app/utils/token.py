"""Token 计算和消息截断工具"""
import os
import json
from pathlib import Path
from urllib.error import URLError, HTTPError

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
    # 本地 token 文件目录路径
    LOCAL_TOKEN_DIR = Path(__file__).parent.parent.parent / "data" / "token"
    # encoding 缓存字典
    _encoding_map: dict[str, tiktoken.Encoding] = {}

    def __init__(self, model: str):
        """
        初始化 Token 计算器

        Args:
            model: 模型名称
        """
        self.model = model
        self.encoding = self._get_encoding(model)

    @classmethod
    def _get_cached_encoding(cls, key: str) -> tiktoken.Encoding | None:
        """
        从缓存中获取 encoding

        Args:
            key: 缓存键（模型名称或 encoding 名称）

        Returns:
            tiktoken.Encoding 对象，如果不存在则返回 None
        """
        return cls._encoding_map.get(key)

    @classmethod
    def _set_cached_encoding(cls, key: str, encoding: tiktoken.Encoding) -> None:
        """
        将 encoding 存储到缓存中

        Args:
            key: 缓存键（模型名称或 encoding 名称）
            encoding: tiktoken.Encoding 对象
        """
        cls._encoding_map[key] = encoding
        logger.debug(f"已将 encoding 缓存: {key}")

    def _get_encoding(self, model: str) -> tiktoken.Encoding:
        # 首先检查缓存中是否已有该模型的 encoding
        cached_encoding = self._get_cached_encoding(model)
        if cached_encoding is not None:
            logger.debug(f"从缓存中获取模型 {model} 的 encoding")
            return cached_encoding

        try:
            encoding = tiktoken.encoding_for_model(model)
            # 成功加载后，存储到缓存中
            self._set_cached_encoding(model, encoding)
            logger.debug(f"成功加载模型 {model} 的 encoding 并缓存")
            return encoding
        except KeyError:
            # 如果模型无法自动映射，使用默认的 encoding
            # 大多数现代模型（包括 Qwen）使用 cl100k_base
            logger.warning(
                f"无法自动映射模型 {model} 到 tokenizer，使用默认 encoding: {self.DEFAULT_ENCODING_NAME}"
            )
            encoding = self._get_encoding_with_fallback(
                self.DEFAULT_ENCODING_NAME)
            # 将默认 encoding 也缓存到模型名下
            self._set_cached_encoding(model, encoding)
            return encoding
        except (ConnectionError, TimeoutError, URLError, HTTPError) as e:
            # 捕获网络错误，尝试从本地加载
            logger.warning(
                f"加载模型 {model} 的 encoding 时发生网络错误: {e}，尝试从本地加载"
            )
            encoding = self._get_encoding_with_fallback(
                self.DEFAULT_ENCODING_NAME)
            # 将本地加载的 encoding 也缓存到模型名下
            self._set_cached_encoding(model, encoding)
            return encoding
        except OSError as e:
            # 捕获文件系统相关的错误（可能包括网络相关的 OSError）
            # 检查是否是网络相关的错误
            error_str = str(e).lower()
            if any(
                keyword in error_str
                for keyword in ["connection", "network", "timeout", "unreachable", "refused"]
            ):
                logger.warning(
                    f"加载模型 {model} 的 encoding 时发生网络错误: {e}，尝试从本地加载"
                )
                encoding = self._get_encoding_with_fallback(
                    self.DEFAULT_ENCODING_NAME)
                # 将本地加载的 encoding 也缓存到模型名下
                self._set_cached_encoding(model, encoding)
                return encoding
            # 如果不是网络错误，重新抛出
            raise
        except Exception as e:
            # 捕获其他未知异常，尝试从本地加载
            logger.warning(
                f"加载模型 {model} 的 encoding 时发生未知错误: {e}，尝试从本地加载"
            )
            encoding = self._get_encoding_with_fallback(
                self.DEFAULT_ENCODING_NAME)
            # 将本地加载的 encoding 也缓存到模型名下
            self._set_cached_encoding(model, encoding)
            return encoding

    def _get_encoding_with_fallback(self, encoding_name: str) -> tiktoken.Encoding:
        """
        尝试从本地加载 encoding，如果本地文件不存在则回退到默认方式

        Args:
            encoding_name: encoding 名称，如 "cl100k_base"

        Returns:
            tiktoken.Encoding 对象
        """
        # 首先检查缓存中是否已有该 encoding_name 的 encoding
        cached_encoding = self._get_cached_encoding(encoding_name)
        if cached_encoding is not None:
            logger.debug(f"从缓存中获取 encoding: {encoding_name}")
            return cached_encoding

        # 检查本地 token 目录是否存在
        if self.LOCAL_TOKEN_DIR.exists() and self.LOCAL_TOKEN_DIR.is_dir():
            local_token_file = self.LOCAL_TOKEN_DIR / \
                f"{encoding_name}.tiktoken"
            if local_token_file.exists():
                try:
                    # 设置 TIKTOKEN_CACHE_DIR 环境变量，让 tiktoken 从本地目录加载
                    original_cache_dir = os.environ.get("TIKTOKEN_CACHE_DIR")
                    os.environ["TIKTOKEN_CACHE_DIR"] = str(
                        self.LOCAL_TOKEN_DIR)
                    logger.info(
                        f"从本地目录加载 encoding: {local_token_file}，缓存目录: {self.LOCAL_TOKEN_DIR}"
                    )
                    encoding = tiktoken.get_encoding(encoding_name)
                    # 恢复原始缓存目录（如果存在）
                    if original_cache_dir is not None:
                        os.environ["TIKTOKEN_CACHE_DIR"] = original_cache_dir
                    elif "TIKTOKEN_CACHE_DIR" in os.environ:
                        del os.environ["TIKTOKEN_CACHE_DIR"]
                    # 成功加载后，存储到缓存中
                    self._set_cached_encoding(encoding_name, encoding)
                    return encoding
                except Exception as e:
                    logger.warning(
                        f"从本地文件加载 encoding 失败: {e}，回退到默认方式"
                    )
                    # 恢复原始缓存目录
                    if original_cache_dir is not None:
                        os.environ["TIKTOKEN_CACHE_DIR"] = original_cache_dir
                    elif "TIKTOKEN_CACHE_DIR" in os.environ:
                        del os.environ["TIKTOKEN_CACHE_DIR"]

        # 如果本地加载失败，尝试默认方式（可能会再次尝试网络请求）
        try:
            encoding = tiktoken.get_encoding(encoding_name)
            # 成功加载后，存储到缓存中
            self._set_cached_encoding(encoding_name, encoding)
            return encoding
        except Exception as e:
            logger.error(f"无法加载 encoding {encoding_name}: {e}")
            raise

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
