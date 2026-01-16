"""工具结果上下文压缩与相关性过滤"""

from __future__ import annotations

from dataclasses import dataclass

from langchain_community.embeddings import DashScopeEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_text_splitters import MarkdownTextSplitter

from app.schemas.config import CompressionConfig, EmbeddingModelConfig
from app.utils.token import TokenCalculator


@dataclass
class CompactionResult:
    content: str
    relevance_applied: bool
    threshold_token_count: int
    original_token_count: int
    relevant_token_count: int


class ContextCompactor:
    """基于相关性过滤的上下文压缩器（工具返回为 markdown）"""

    def __init__(
        self,
        embedding_model: EmbeddingModelConfig,
        compression_config: CompressionConfig,
    ) -> None:
        self.embedding_model = embedding_model
        self.compression_config = compression_config
        self.embeddings = DashScopeEmbeddings(
            model=embedding_model.model_name,
            dashscope_api_key=embedding_model.api_key,
        )
        self.token_calculator = TokenCalculator(embedding_model.model_name)

    def _split_markdown(self, content: str) -> list[str]:
        splitter = MarkdownTextSplitter(chunk_size=1000, chunk_overlap=200)
        return [
            chunk.strip() for chunk in splitter.split_text(content) if chunk.strip()
        ]

    def extract_relevant_markdown(self, query: str, content: str) -> str:
        if not content.strip():
            return content

        chunks = self._split_markdown(content)
        if not chunks:
            return content

        documents = [
            Document(page_content=chunk, metadata={"index": idx})
            for idx, chunk in enumerate(chunks)
        ]
        vector_store = FAISS.from_documents(documents, self.embeddings)
        results = vector_store.similarity_search_with_score(query, k=len(documents))

        if not results:
            return chunks[0]

        max_tokens = self.compression_config.tool_result_max_tokens
        sorted_relevant = sorted(
            results, key=lambda item: item[1]
        )  # score 越小相似度越高
        selected_chunks: list[tuple[int, str]] = []
        selected_tokens = 0
        for doc, _score in sorted_relevant:
            chunk_text = doc.page_content
            chunk_tokens = self.token_calculator.count_tokens(chunk_text)
            if selected_tokens + chunk_tokens > max_tokens:
                continue
            selected_chunks.append((doc.metadata["index"], chunk_text))
            selected_tokens += chunk_tokens

        if not selected_chunks:
            return chunks[0]

        selected_sorted = sorted(selected_chunks, key=lambda item: item[0])
        return "\n\n".join(item[1] for item in selected_sorted)

    async def compact_markdown_tool_result(
        self,
        query: str,
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
                original_token_count=original_tokens,
                relevant_token_count=original_tokens,
                threshold_token_count=threshold_tokens,
            )

        relevant_content = self.extract_relevant_markdown(query, content)
        relevant_tokens = self.token_calculator.count_tokens(relevant_content)
        return CompactionResult(
            content=relevant_content,
            relevance_applied=self.compression_config.relevance_enabled,
            original_token_count=original_tokens,
            relevant_token_count=relevant_tokens,
            threshold_token_count=threshold_tokens,
        )
