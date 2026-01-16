"""工具结果上下文压缩与相关性过滤"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from pathlib import Path

import aiofiles
from openai import AsyncOpenAI

from app.schemas.config import CompressionConfig, SummarizerModelConfig
from app.utils.token import TokenCalculator


@dataclass
class CompactionResult:
    content: str
    relevance_applied: bool
    summary_applied: bool
    reference_id: str | None
    threshold_token_count: int
    original_token_count: int
    relevant_token_count: int
    summary_token_count: int | None


class ContextCompactor:
    """基于相关性过滤与摘要的上下文压缩器（工具返回为 markdown）"""

    def __init__(
        self,
        summarizer_model: SummarizerModelConfig,
        compression_config: CompressionConfig,
    ) -> None:
        self.summarizer_model = summarizer_model
        self.compression_config = compression_config
        self.client = AsyncOpenAI(
            api_key=summarizer_model.api_key,
            base_url=summarizer_model.api_base,
        )
        self.token_calculator = TokenCalculator(summarizer_model.model_name)

    def _split_markdown(self, content: str) -> list[str]:
        chunks = [chunk.strip() for chunk in re.split(r"\n{2,}", content) if chunk]
        return chunks

    def _tokenize_query(self, query: str) -> list[str]:
        query = query.strip()
        latin_tokens = re.findall(r"[A-Za-z0-9_]+", query.lower())
        latin_tokens = [token for token in latin_tokens if len(token) > 1]
        cjk_tokens = re.findall(r"[\u4e00-\u9fff]", query)
        tokens = latin_tokens + cjk_tokens
        if not tokens and query:
            tokens = [query]
        return tokens

    def _score_chunk(self, chunk: str, tokens: list[str]) -> int:
        if not tokens:
            return 0
        chunk_lower = chunk.lower()
        score = 0
        for token in tokens:
            if re.fullmatch(r"[\u4e00-\u9fff]", token):
                score += chunk.count(token)
            else:
                score += chunk_lower.count(token)
        return score

    def extract_relevant_markdown(self, query: str, content: str) -> str:
        if not content.strip():
            return content

        chunks = self._split_markdown(content)
        if not chunks:
            return content

        tokens = self._tokenize_query(query)
        scored_chunks = []
        for idx, chunk in enumerate(chunks):
            score = self._score_chunk(chunk, tokens)
            scored_chunks.append((idx, score, chunk))

        relevant = [item for item in scored_chunks if item[1] > 0]
        if not relevant:
            return chunks[0]

        max_tokens = self.compression_config.tool_result_max_tokens
        sorted_relevant = sorted(relevant, key=lambda item: item[1], reverse=True)
        selected_chunks: list[tuple[int, int, str]] = []
        selected_tokens = 0
        for item in sorted_relevant:
            chunk_tokens = self.token_calculator.count_tokens(item[2])
            if selected_tokens + chunk_tokens > max_tokens:
                continue
            selected_chunks.append(item)
            selected_tokens += chunk_tokens

        if not selected_chunks:
            return chunks[0]

        selected_sorted = sorted(selected_chunks, key=lambda item: item[0])
        return "\n\n".join(item[2] for item in selected_sorted)

    async def _write_reference(
        self, tool_name: str, content: str, query: str
    ) -> str | None:
        if not self.compression_config.reference_enabled:
            return None

        base_dir = Path(self.compression_config.reference_dir)
        base_dir.mkdir(parents=True, exist_ok=True)
        reference_id = f"{tool_name}-{uuid.uuid4().hex}"
        file_path = base_dir / f"{reference_id}.md"
        header = f"<!-- tool: {tool_name} | query: {query} -->\n\n"

        async with aiofiles.open(file_path, "w", encoding="utf-8") as f:
            await f.write(header + content)

        return reference_id

    async def compact_markdown_tool_result(
        self,
        query: str,
        tool_name: str,
        content: str,
    ) -> CompactionResult:
        original_tokens = self.token_calculator.count_tokens(content)
        threshold_tokens = self.compression_config.tool_result_max_tokens

        if (
            not self.compression_config.enabled
            or original_tokens <= threshold_tokens
            or not self.compression_config.relevance_enabled
        ):
            return CompactionResult(
                content=content,
                relevance_applied=self.compression_config.relevance_enabled,
                summary_applied=False,
                reference_id=None,
                original_token_count=original_tokens,
                relevant_token_count=original_tokens,
                summary_token_count=None,
                threshold_token_count=threshold_tokens,
            )

        relevant_content = self.extract_relevant_markdown(query, content)
        relevant_tokens = self.token_calculator.count_tokens(relevant_content)
        if relevant_tokens <= threshold_tokens:
            return CompactionResult(
                content=relevant_content,
                relevance_applied=self.compression_config.relevance_enabled,
                summary_applied=False,
                reference_id=None,
                original_token_count=original_tokens,
                relevant_token_count=relevant_tokens,
                summary_token_count=None,
                threshold_token_count=threshold_tokens,
            )

        reference_id = await self._write_reference(tool_name, content, query)

        return CompactionResult(
            content=relevant_content,
            relevance_applied=self.compression_config.relevance_enabled,
            summary_applied=False,
            reference_id=reference_id,
            original_token_count=original_tokens,
            relevant_token_count=relevant_tokens,
            summary_token_count=None,
            threshold_token_count=threshold_tokens,
        )
