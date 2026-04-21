"""Token 计算和消息截断工具"""

import base64
import json
import math
import os
from collections.abc import Sequence
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError

import tiktoken
from PIL import Image
from pydantic import BaseModel

from app.utils.common import normalize_to_dict
from app.utils.logger import logger


class TokenCalculator:
    """Token 计算工具类"""

    # encoding 缓存字典，作为类变量，便于多个 TokenCalculator 实例共享
    _encoding_map: dict[str, tiktoken.Encoding] = {}

    # 常见模型的上下文限制
    MODEL_LIMITS = {
        "deepseek-chat": 131072,
        "deepseek-reasoner": 131072,
        "qwen-plus": 1000000,
        "qwen-flash": 1000000,
        "qwen3.5-flash": 1000000,
        "qwen3.6-flash": 1000000,
        "qwen3.6-plus": 1000000,
        "qwen-turbo": 128000,  # 纯文本模型
    }

    DEFAULT_LIMIT = 131072  # deepseek 的默认限制
    DEFAULT_ENCODING_NAME = "cl100k_base"
    IMAGE_PATCH_SIZE = 28
    IMAGE_FIXED_TOKEN_OVERHEAD = 2
    # 本地 token 文件目录路径
    LOCAL_TOKEN_DIR = Path(__file__).parent.parent.parent / "data" / "token"

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
            encoding = self._get_encoding_with_fallback(self.DEFAULT_ENCODING_NAME)
            # 将默认 encoding 也缓存到模型名下
            self._set_cached_encoding(model, encoding)
            return encoding
        except (ConnectionError, TimeoutError, URLError, HTTPError) as e:
            # 捕获网络错误，尝试从本地加载
            logger.warning(
                f"加载模型 {model} 的 encoding 时发生网络错误: {e}，尝试从本地加载"
            )
            encoding = self._get_encoding_with_fallback(self.DEFAULT_ENCODING_NAME)
            # 将本地加载的 encoding 也缓存到模型名下
            self._set_cached_encoding(model, encoding)
            return encoding
        except OSError as e:
            # 捕获文件系统相关的错误（可能包括网络相关的 OSError）
            # 检查是否是网络相关的错误
            error_str = str(e).lower()
            if any(
                keyword in error_str
                for keyword in [
                    "connection",
                    "network",
                    "timeout",
                    "unreachable",
                    "refused",
                ]
            ):
                logger.warning(
                    f"加载模型 {model} 的 encoding 时发生网络错误: {e}，尝试从本地加载"
                )
                encoding = self._get_encoding_with_fallback(self.DEFAULT_ENCODING_NAME)
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
            encoding = self._get_encoding_with_fallback(self.DEFAULT_ENCODING_NAME)
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
            local_token_file = self.LOCAL_TOKEN_DIR / f"{encoding_name}.tiktoken"
            if local_token_file.exists():
                try:
                    # 直接从本地文件加载 encoding，避免网络请求
                    logger.info(f"从本地文件直接加载 encoding: {local_token_file}")
                    encoding = self._load_encoding_from_local_file(
                        encoding_name, local_token_file
                    )
                    # 成功加载后，存储到缓存中
                    self._set_cached_encoding(encoding_name, encoding)
                    return encoding
                except Exception as e:
                    logger.warning(f"从本地文件加载 encoding 失败: {e}，回退到默认方式")

        # 如果本地加载失败，尝试默认方式（可能会再次尝试网络请求）
        try:
            encoding = tiktoken.get_encoding(encoding_name)
            # 成功加载后，存储到缓存中
            self._set_cached_encoding(encoding_name, encoding)
            return encoding
        except Exception as e:
            logger.error(f"无法加载 encoding {encoding_name}: {e}")
            raise

    def _load_encoding_from_local_file(
        self, encoding_name: str, local_file: Path
    ) -> tiktoken.Encoding:
        """
        从本地文件直接加载 encoding，避免网络请求

        Args:
            encoding_name: encoding 名称，如 "cl100k_base"
            local_file: 本地 .tiktoken 文件路径

        Returns:
            tiktoken.Encoding 对象
        """
        # 目前只支持 cl100k_base，其他编码可以后续扩展
        if encoding_name == "cl100k_base":
            # cl100k_base 的配置（来自 tiktoken_ext/openai_public.py）
            ENDOFTEXT = "<|endoftext|>"
            FIM_PREFIX = "<|fim_prefix|>"
            FIM_MIDDLE = "<|fim_middle|>"
            FIM_SUFFIX = "<|fim_suffix|>"
            ENDOFPROMPT = "<|endofprompt|>"

            pat_str = r"""'(?i:[sdmt]|ll|ve|re)|[^\r\n\p{L}\p{N}]?+\p{L}++|\p{N}{1,3}+| ?[^\s\p{L}\p{N}]++[\r\n]*+|\s++$|\s*[\r\n]|\s+(?!\S)|\s"""
            special_tokens = {
                ENDOFTEXT: 100257,
                FIM_PREFIX: 100258,
                FIM_MIDDLE: 100259,
                FIM_SUFFIX: 100260,
                ENDOFPROMPT: 100276,
            }

            # 从本地文件直接读取并解析 BPE ranks
            mergeable_ranks = self._load_bpe_from_local_file(local_file)

            # 创建 Encoding 对象
            encoding = tiktoken.Encoding(
                name=encoding_name,
                pat_str=pat_str,
                mergeable_ranks=mergeable_ranks,
                special_tokens=special_tokens,
            )
            return encoding
        else:
            # 对于其他编码，尝试使用默认方式（但会设置缓存目录）
            original_cache_dir = os.environ.get("TIKTOKEN_CACHE_DIR")
            try:
                os.environ["TIKTOKEN_CACHE_DIR"] = str(self.LOCAL_TOKEN_DIR)
                encoding = tiktoken.get_encoding(encoding_name)
                return encoding
            finally:
                if original_cache_dir is not None:
                    os.environ["TIKTOKEN_CACHE_DIR"] = original_cache_dir
                elif "TIKTOKEN_CACHE_DIR" in os.environ:
                    del os.environ["TIKTOKEN_CACHE_DIR"]

    def _load_bpe_from_local_file(self, local_file: Path) -> dict[bytes, int]:
        """
        从本地 .tiktoken 文件直接读取并解析 BPE ranks

        Args:
            local_file: 本地 .tiktoken 文件路径

        Returns:
            BPE ranks 字典，格式为 {token_bytes: rank}
        """
        mergeable_ranks = {}
        with open(local_file, "rb") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    # 每行格式：base64_encoded_token rank
                    token_b64, rank_str = line.split(b" ", 1)
                    token = base64.b64decode(token_b64)
                    rank = int(rank_str)
                    mergeable_ranks[token] = rank
                except Exception as e:
                    raise ValueError(
                        f"解析本地 BPE 文件失败，行内容: {line!r}, 错误: {e}"
                    ) from e
        return mergeable_ranks

    def get_max_context_tokens(self) -> int:
        """
        获取模型的最大上下文 token 数量

        Returns:
            最大上下文 token 数量
        """
        model_to_check = self.model.lower()

        # 首先尝试精确匹配
        if model_to_check in self.MODEL_LIMITS:
            return self.MODEL_LIMITS[model_to_check]

        # 如果没有精确匹配，尝试前缀匹配（支持带版本号的模型名）
        # 例如：deepseek-chat-v1 会匹配到 deepseek-chat
        for model_key in self.MODEL_LIMITS:
            if model_to_check.startswith(model_key):
                return self.MODEL_LIMITS[model_key]

        # 默认值：131072（deepseek 的默认限制）
        return self.DEFAULT_LIMIT

    def get_compression_threshold(self, threshold_ratio: float) -> int:
        """
        获取压缩阈值
        """
        return int(self.get_max_context_tokens() * threshold_ratio)

    def count_tokens(self, text: str | None) -> int:
        """
        计算文本的 token 数量

        Args:
            text: 要计算的文本

        Returns:
            token 数量
        """
        return len(self.encoding.encode(text or ""))

    def count_message_tokens(self, message: dict[str, Any] | BaseModel) -> int:
        total_tokens = 0
        message = normalize_to_dict(message)
        content_blocks = message.get("content_blocks")
        if content_blocks is not None:
            total_tokens += self.count_tokens(json.dumps(content_blocks))
        else:
            content = message.get("content", "")
            if isinstance(content, list):
                total_tokens += self._count_multimodal_content_tokens(content)
            elif isinstance(content, str):
                total_tokens += self.count_tokens(content)
            else:
                total_tokens += self.count_tokens(
                    json.dumps(content, ensure_ascii=False)
                )
            total_tokens += self.count_tokens(message.get("reasoning", ""))
        total_tokens += self.count_tokens(message.get("reasoning_content", ""))
        total_tokens += self.count_tokens(json.dumps(message.get("tool_calls", [])))
        return total_tokens

    def _count_multimodal_content_tokens(self, content: list[Any]) -> int:
        total = 0
        for part in content:
            if not isinstance(part, dict):
                total += self.count_tokens(json.dumps(part, ensure_ascii=False))
                continue

            part_type = part.get("type")
            if part_type == "text":
                total += self.count_tokens(str(part.get("text", "")))
                continue
            if part_type == "image_url":
                image_url_payload = part.get("image_url", {})
                if isinstance(image_url_payload, dict):
                    image_url = str(image_url_payload.get("url", ""))
                else:
                    image_url = str(image_url_payload or "")
                total += self._count_image_url_tokens(image_url)
                continue
            total += self.count_tokens(json.dumps(part, ensure_ascii=False))
        return total

    def _count_image_url_tokens(self, image_url: str) -> int:
        width_height = self._extract_image_size_from_data_url(image_url)
        if width_height is None:
            return self.count_tokens(image_url)
        width, height = width_height
        return (
            math.ceil(height / self.IMAGE_PATCH_SIZE)
            * math.ceil(width / self.IMAGE_PATCH_SIZE)
            + self.IMAGE_FIXED_TOKEN_OVERHEAD
        )

    def _extract_image_size_from_data_url(
        self, image_url: str
    ) -> tuple[int, int] | None:
        if not image_url.startswith("data:image/"):
            return None
        marker = ";base64,"
        if marker not in image_url:
            return None
        _, _, encoded = image_url.partition(marker)
        if not encoded:
            return None
        try:
            image_bytes = base64.b64decode(encoded, validate=True)
            with Image.open(BytesIO(image_bytes)) as image:
                return image.size
        except Exception as exc:
            logger.warning("Failed to parse image data URL size", error=exc)
            return None

    def count_messages_tokens(
        self, messages: Sequence[dict[str, Any] | BaseModel]
    ) -> int:
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
            total_tokens += self.count_message_tokens(message)

        return total_tokens

    def truncate_text_to_tokens(self, text: str, max_tokens: int) -> str:
        """将文本截断到不超过 max_tokens（按 token 从前往后保留）。"""
        if not text or max_tokens <= 0:
            return ""
        token_ids = self.encoding.encode(text)
        if len(token_ids) <= max_tokens:
            return text
        return self.encoding.decode(token_ids[:max_tokens])
