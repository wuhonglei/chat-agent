"""Context compression utilities for handling tool results and conversation context"""

import json
import re
from enum import Enum
from typing import Any

from pydantic import BaseModel

from app.utils.logger import logger
from app.utils.token import TokenCalculator


class ContentType(str, Enum):
    """Content type enumeration for compression"""

    WEB_CONTENT = "web_content"
    SEARCH_RESULTS = "search_results"
    API_RESPONSE = "api_response"
    GENERIC = "generic"


class CompressionResult(BaseModel):
    """Compression result data structure"""

    original_content: str
    compressed_content: str
    compression_ratio: float
    content_type: ContentType
    processing_time: float
    key_info_extracted: list[str] | None = None


class GenericCompressor:
    """Generic content compressor for various content types"""

    def __init__(self, max_length: int, token_calculator: TokenCalculator):
        self.max_length = max_length
        self.token_calculator = token_calculator

    def compress(
        self, content: str, content_type: ContentType = ContentType.GENERIC
    ) -> CompressionResult:
        """
        Generic content compression
        1. Extract key sentences and core content
        2. Preserve structured data (lists, tables, headings)
        3. Remove duplicate information and redundant content
        4. Intelligently truncate long paragraphs
        5. Filter ads, navigation and irrelevant content
        """
        import time

        start_time = time.time()

        original_length = self.token_calculator.count_tokens(content)

        try:
            # Detect content type
            if content_type == ContentType.GENERIC:
                content_type = GenericCompressor.detect_content_type(content)

            # Apply type-specific compression
            if content_type == ContentType.WEB_CONTENT:
                compressed = self._compress_web_content(content)
            elif content_type == ContentType.SEARCH_RESULTS:
                compressed = self._compress_search_results(content)
            elif content_type == ContentType.API_RESPONSE:
                compressed = self._compress_api_response(content)
            else:
                compressed = self._compress_generic_content(content)

            # Ensure length limit
            compressed_tokens = self.token_calculator.count_tokens(compressed)
            if compressed_tokens > self.max_length:
                compressed = self._intelligent_truncate(compressed, self.max_length)

            compressed_tokens = self.token_calculator.count_tokens(compressed)
            compression_ratio = (
                compressed_tokens / original_length if original_length > 0 else 1.0
            )
            processing_time = time.time() - start_time

            return CompressionResult(
                original_content=content,
                compressed_content=compressed,
                compression_ratio=compression_ratio,
                content_type=content_type,
                processing_time=processing_time,
                key_info_extracted=self._extract_key_info(compressed),
            )

        except Exception as e:
            logger.error("Compression failed", error=str(e), content_type=content_type)
            # Return original content if compression fails
            return CompressionResult(
                original_content=content,
                compressed_content=content[: self.max_length],
                compression_ratio=1.0,
                content_type=content_type,
                processing_time=time.time() - start_time,
            )

    @staticmethod
    def detect_content_type(content: str) -> ContentType:
        """Detect content type based on content patterns"""
        content_lower = content.lower()

        # Web content patterns
        if any(
            pattern in content_lower
            for pattern in ["<html", "<body", "http://", "https://"]
        ):
            return ContentType.WEB_CONTENT

        # Search results patterns
        if any(
            pattern in content_lower
            for pattern in ["search results", "query:", "results for"]
        ):
            return ContentType.SEARCH_RESULTS

        # API response patterns
        if content.strip().startswith(("{", "[")) and content.strip().endswith(
            ("}", "]")
        ):
            try:
                json.loads(content)
                return ContentType.API_RESPONSE
            except:
                pass

        return ContentType.GENERIC

    def _compress_web_content(self, content: str) -> str:
        """Compress web content by removing navigation, ads, and boilerplate"""
        # Remove common web elements
        content = re.sub(
            r"<script[^>]*>.*?</script>", "", content, flags=re.DOTALL | re.IGNORECASE
        )
        content = re.sub(
            r"<style[^>]*>.*?</style>", "", content, flags=re.DOTALL | re.IGNORECASE
        )
        content = re.sub(
            r"<nav[^>]*>.*?</nav>", "", content, flags=re.DOTALL | re.IGNORECASE
        )
        content = re.sub(
            r"<header[^>]*>.*?</header>", "", content, flags=re.DOTALL | re.IGNORECASE
        )
        content = re.sub(
            r"<footer[^>]*>.*?</footer>", "", content, flags=re.DOTALL | re.IGNORECASE
        )
        content = re.sub(
            r"<aside[^>]*>.*?</aside>", "", content, flags=re.DOTALL | re.IGNORECASE
        )

        # Remove HTML tags but keep content
        content = re.sub(r"<[^>]+>", " ", content)

        # Clean up whitespace
        content = re.sub(r"\s+", " ", content).strip()

        # Extract main content (simple heuristic)
        lines = content.split("\n")
        main_content_lines = []

        for line in lines:
            line = line.strip()
            if len(line) < 10:  # Skip very short lines
                continue
            if any(
                skip_word in line.lower()
                for skip_word in [
                    "copyright",
                    "privacy policy",
                    "terms of service",
                    "advertisement",
                    "cookie",
                ]
            ):
                continue
            main_content_lines.append(line)

        return "\n".join(main_content_lines)

    def _compress_search_results(self, content: str) -> str:
        """Compress search results by keeping top results and key information"""
        lines = content.split("\n")
        compressed_lines = []
        result_count = 0
        max_results = 10  # Keep top 10 results

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Keep result headers and summaries
            if any(
                indicator in line.lower()
                for indicator in [
                    "title:",
                    "url:",
                    "snippet:",
                    "description:",
                    "summary:",
                ]
            ):
                compressed_lines.append(line)
                if "title:" in line.lower():
                    result_count += 1
                    if result_count >= max_results:
                        break

        return "\n".join(compressed_lines)

    def _compress_api_response(self, content: str) -> str:
        """Compress API response by extracting key fields"""
        try:
            data = json.loads(content)
            # Simple API response compression - keep structure but limit depth
            json_str = json.dumps(data, indent=2, ensure_ascii=False)
            # Truncate based on tokens
            if self.token_calculator.count_tokens(json_str) > self.max_length:
                return self._intelligent_truncate(json_str, self.max_length)
            return json_str
        except:
            # Fallback: truncate based on tokens
            if self.token_calculator.count_tokens(content) > self.max_length:
                return self._intelligent_truncate(content, self.max_length)
            return content

    def _compress_generic_content(self, content: str) -> str:
        """Generic content compression using simple heuristics"""
        # Split into sentences
        sentences = re.split(r"[.!?]+", content)
        sentences = [s.strip() for s in sentences if s.strip()]

        # Keep sentences with high information density
        compressed_sentences = []
        for sentence in sentences:
            # Skip very short sentences
            if len(sentence) < 10:
                continue
            # Skip sentences that look like boilerplate
            if any(
                skip_pattern in sentence.lower()
                for skip_pattern in [
                    "please try again",
                    "loading",
                    "error occurred",
                    "system message",
                ]
            ):
                continue
            compressed_sentences.append(sentence)

            # Limit total length
            current_text = " ".join(compressed_sentences)
            if self.token_calculator.count_tokens(current_text) > self.max_length * 0.8:
                break

        return ". ".join(compressed_sentences)

    def _intelligent_truncate(self, content: str, max_length: int) -> str:
        """Intelligently truncate content to max_length (in tokens)"""
        if self.token_calculator.count_tokens(content) <= max_length:
            return content

        # Try to truncate at sentence boundaries
        sentences = re.split(r"[.!?]+", content)
        truncated = ""
        for sentence in sentences:
            test_text = truncated + sentence + ". "
            if self.token_calculator.count_tokens(test_text) > max_length:
                break
            truncated = test_text

        if len(truncated) > 0:
            return truncated.rstrip()
        else:
            # Fallback to hard truncation based on tokens
            # Gradually truncate character by character until token limit is reached
            truncated_content = ""
            for char in content:
                test_content = truncated_content + char
                if self.token_calculator.count_tokens(test_content) > max_length:
                    break
                truncated_content = test_content
            # Final fallback to first 100 chars
            return truncated_content if truncated_content else content[:100]

    def _extract_key_info(self, content: str) -> list[str]:
        """Extract key information from compressed content"""
        key_info = []

        # Extract URLs
        urls = re.findall(r"https?://[^\s]+", content)
        key_info.extend(urls)

        # Extract dates
        dates = re.findall(r"\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4}", content)
        key_info.extend(dates)

        # Extract key phrases (simple heuristic)
        words = re.findall(r"\b[A-Z][a-z]+\s+[A-Z][a-z]+\b", content)
        key_info.extend(words[:5])  # Limit to 5 key phrases

        return list(set(key_info))  # Remove duplicates


class IterationCompressor:
    """Compressor for MCP tool iteration contexts"""

    def __init__(self, max_context_length: int, token_calculator: TokenCalculator):
        self.max_context_length = max_context_length
        self.token_calculator = token_calculator

    def compress_iteration_context(
        self,
        current_iteration_results: list[dict[str, Any]],
        historical_context: list[dict[str, Any]],
        iteration: int,
        max_context_length: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        Compress context between MCP tool iterations
        1. Keep current iteration results mostly intact
        2. Compress historical iteration results progressively
        3. Remove duplicate and irrelevant information
        4. Ensure total context length doesn't exceed threshold
        """
        max_length = max_context_length or self.max_context_length

        compressed_context = []

        # Process historical context (older iterations)
        for _i, hist_result in enumerate(historical_context):
            age = iteration - hist_result.get("iteration", 0)
            retention_ratio = self._get_retention_ratio(age)

            if retention_ratio > 0:
                compressed_result = self._compress_single_result(
                    hist_result, retention_ratio
                )
                compressed_context.append(compressed_result)

        # Add current iteration results (keep most intact)
        for result in current_iteration_results:
            compressed_context.append(result)

        # Ensure total length doesn't exceed limit
        return self._ensure_total_length(compressed_context, max_length)

    def _get_retention_ratio(self, age: int) -> float:
        """Get retention ratios based on iteration age"""
        config = {
            0: 0.9,  # Current iteration
            1: 0.7,  # 1 iteration ago
            2: 0.5,  # 2 iterations ago
            3: 0.3,  # 3+ iterations ago
        }
        return config.get(age, 0.3)

    def _compress_single_result(self, result: dict, retention_ratio: float) -> dict:
        """Compress a single tool result based on retention ratio"""
        compressed = result.copy()

        # Compress content field if it exists
        if "content" in compressed and isinstance(compressed["content"], str):
            original_length = self.token_calculator.count_tokens(compressed["content"])
            target_length = int(original_length * retention_ratio)

            if target_length < original_length:
                # Convert string content_type to enum, fallback to GENERIC
                content_type_str = result.get("content_type", ContentType.GENERIC.value)
                try:
                    content_type_enum = ContentType(content_type_str)
                except ValueError:
                    content_type_enum = ContentType.GENERIC

                compressor = GenericCompressor(
                    max_length=target_length, token_calculator=self.token_calculator
                )
                compression_result = compressor.compress(
                    compressed["content"], content_type=content_type_enum
                )
                compressed["content"] = compression_result.compressed_content
                compressed["compression_info"] = {
                    "original_length": original_length,
                    "compressed_length": self.token_calculator.count_tokens(
                        compression_result.compressed_content
                    ),
                    "compression_ratio": compression_result.compression_ratio,
                }

        return compressed

    def _ensure_total_length(
        self, context: list[dict[str, Any]], max_length: int
    ) -> list[dict[str, Any]]:
        """Ensure total context length doesn't exceed max_length (in tokens)"""

        total_length = self.token_calculator.count_messages_tokens(context)

        if total_length <= max_length:
            return context

        # Remove oldest results until under limit
        sorted_context = sorted(context, key=lambda x: x.get("iteration", 0))
        compressed_context = []

        for result in reversed(sorted_context):  # Start from most recent
            compressed_context.insert(0, result)
            current_length = self.token_calculator.count_messages_tokens(
                compressed_context
            )

            if current_length > max_length:
                # Remove the oldest result if still over limit
                if len(compressed_context) > 1:
                    compressed_context.pop(0)
                break

        return compressed_context


class ContextMonitor:
    """Monitor context length and trigger compression"""

    def __init__(self, token_calculator: TokenCalculator, compression_threshold: int):
        self.token_calculator = token_calculator
        self.compression_threshold = compression_threshold
        self.max_context_length = token_calculator.get_max_context_tokens()

    def check_and_compress(
        self, messages: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """
        Check context length and compress if needed
        1. Estimate token count
        2. Trigger compression if over threshold
        3. Return compressed results
        """
        total_tokens = self.token_calculator.count_messages_tokens(messages)

        if total_tokens < self.compression_threshold:
            return messages

        logger.info(
            "Context length exceeds threshold, triggering compression",
            total_tokens=total_tokens,
            threshold=self.compression_threshold,
        )

        # Compress results
        compressor = GenericCompressor(
            max_length=self.compression_threshold // len(messages) or 1000,
            token_calculator=self.token_calculator,
        )

        compressed_results = []
        for result in messages:
            if isinstance(result.get("content"), str):
                # Convert string content_type to enum, fallback to GENERIC
                content_type_str = result.get("content_type", ContentType.GENERIC.value)
                try:
                    content_type_enum = ContentType(content_type_str)
                except ValueError:
                    content_type_enum = ContentType.GENERIC

                compression_result = compressor.compress(
                    result["content"], content_type=content_type_enum
                )
                compressed_result = result.copy()
                compressed_result["content"] = compression_result.compressed_content
                compressed_result["compression_info"] = {
                    "original_length": self.token_calculator.count_tokens(
                        result["content"]
                    ),
                    "compressed_length": self.token_calculator.count_tokens(
                        compression_result.compressed_content
                    ),
                    "compression_ratio": compression_result.compression_ratio,
                }
                compressed_results.append(compressed_result)
            else:
                compressed_results.append(result)

        return compressed_results
