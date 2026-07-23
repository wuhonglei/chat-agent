"""工具结果上下文压缩与相关性过滤"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

from langchain_community.embeddings import DashScopeEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_text_splitters import MarkdownTextSplitter
from pydantic import BaseModel

from app.core.observability import mark_observation_error, observation_span
from app.schemas.config import EmbeddingModelConfig, ToolResultCompressionConfig
from app.utils.token import TokenCalculator


class CompactionResult(BaseModel):
    content: str
    summary: str | None = None
    structured_content_for_display: list[dict[str, object]] | None = None
    content_token_count: int
    relevance_applied: bool
    threshold_token_count: int
    original_token_count: int
    relevant_token_count: int


class ContextCompactor:
    """基于相关性过滤的上下文压缩器（工具返回为 markdown）"""

    def __init__(
        self,
        embedding_model: EmbeddingModelConfig,
        tool_result_compression_config: ToolResultCompressionConfig,
    ) -> None:
        self.embedding_model = embedding_model
        self.tool_result_compression_config = tool_result_compression_config
        self.embeddings = DashScopeEmbeddings(
            model=embedding_model.model_name,
            dashscope_api_key=embedding_model.api_key,
        )
        self.token_calculator = TokenCalculator(
            embedding_model.model_name, embedding_model.context_limit
        )

    def _split_markdown(self, content: str) -> list[str]:
        cfg = self.tool_result_compression_config
        splitter = MarkdownTextSplitter(
            chunk_size=cfg.markdown_chunk_size,
            chunk_overlap=cfg.markdown_chunk_overlap,
        )
        return [
            chunk.strip() for chunk in splitter.split_text(content) if chunk.strip()
        ]

    def extract_relevant_markdown(
        self, query: str, content: str, threshold_tokens_count: int
    ) -> str:
        if not content.strip():
            return content

        chunks = self._split_markdown(content)
        if not chunks:
            return content

        with observation_span(
            "tool-result-embedding",
            input={
                "model": self.embedding_model.model_name,
                "query_length": len(query),
                "chunk_count": len(chunks),
            },
        ) as span:
            try:
                documents = [
                    Document(page_content=chunk, metadata={"index": idx})
                    for idx, chunk in enumerate(chunks)
                ]

                cfg = self.tool_result_compression_config
                batch_size = cfg.embedding_batch_size
                max_workers = cfg.embedding_max_workers

                if len(documents) <= batch_size:
                    vector_store = FAISS.from_documents(documents, self.embeddings)
                else:
                    batches = [
                        documents[i : i + batch_size]
                        for i in range(0, len(documents), batch_size)
                    ]
                    stores: list[FAISS] = []

                    # 并行向量化所有批次
                    with ThreadPoolExecutor(max_workers=max_workers) as executor:
                        future_to_idx = {
                            executor.submit(
                                FAISS.from_documents, batch, self.embeddings
                            ): idx
                            for idx, batch in enumerate(batches)
                        }
                        # 按顺序收集结果
                        results_map = {}
                        for future in as_completed(future_to_idx):
                            idx = future_to_idx[future]
                            results_map[idx] = future.result()
                        stores = [results_map[i] for i in range(len(batches))]

                    # 合并索引
                    vector_store = stores[0]
                    for store in stores[1:]:
                        vector_store.merge_from(store)

                results = vector_store.similarity_search_with_score(
                    query, k=len(documents)
                )
            except Exception as exc:
                mark_observation_error(span, exc)
                raise

            if not results:
                if span is not None:
                    span.update(
                        output={"selected_chunks": 0, "relevance_applied": False}
                    )
                return chunks[0]

            sorted_relevant = sorted(
                results, key=lambda item: item[1]
            )  # score 越小相似度越高
            selected_chunks: list[tuple[int, str]] = []
            selected_tokens = 0
            for doc, _score in sorted_relevant:
                chunk_text = doc.page_content
                chunk_tokens = self.token_calculator.count_tokens(chunk_text)
                if selected_tokens + chunk_tokens > threshold_tokens_count:
                    continue
                selected_chunks.append((doc.metadata["index"], chunk_text))
                selected_tokens += chunk_tokens

            if not selected_chunks:
                if span is not None:
                    span.update(
                        output={"selected_chunks": 0, "relevance_applied": False}
                    )
                return chunks[0]

            if span is not None:
                span.update(
                    output={
                        "selected_chunks": len(selected_chunks),
                        "relevance_applied": True,
                    }
                )
            selected_sorted = sorted(selected_chunks, key=lambda item: item[0])
            return "\n\n".join(item[1] for item in selected_sorted)

    async def compact_markdown_tool_result(
        self,
        query: str,
        content: str,
        tolerance_tokens_count: int,
        threshold_tokens_count: int,
    ) -> CompactionResult:
        original_tokens_count = self.token_calculator.count_tokens(content)

        if (
            not self.tool_result_compression_config.enabled
            or original_tokens_count <= tolerance_tokens_count
        ):
            return CompactionResult(
                content=content,
                relevance_applied=False,
                content_token_count=original_tokens_count,
                original_token_count=original_tokens_count,
                relevant_token_count=original_tokens_count,
                threshold_token_count=tolerance_tokens_count,
            )

        relevant_content = self.extract_relevant_markdown(
            query, content, threshold_tokens_count
        )
        relevant_tokens_count = self.token_calculator.count_tokens(relevant_content)
        return CompactionResult(
            content=relevant_content,
            relevance_applied=True,
            content_token_count=relevant_tokens_count,
            original_token_count=original_tokens_count,
            relevant_token_count=relevant_tokens_count,
            threshold_token_count=threshold_tokens_count,
        )
