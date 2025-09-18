"""Chat service for RAG-based Q&A"""

import json
from collections.abc import AsyncGenerator
from datetime import datetime

from loguru import logger
from openai import AsyncOpenAI

from app.core.config import settings
from app.core.vector_store import VectorStore
from app.models.chat import ChatMessage, ChatResponse, SourceConfig
from app.models.retrieval import RetrievalRequest, RetrievalSource
from app.services.reranker import Reranker
from app.services.retrieval_manager import RetrievalManager


class ChatService:
    """Handle chat interactions with RAG"""

    def __init__(self, vector_store: VectorStore):
        self.vector_store = vector_store
        self.client = AsyncOpenAI(
            api_key=settings.LLM_API_KEY,
            base_url=settings.LLM_API_BASE,
        )
        self.reranker = Reranker()
        self.retrieval_manager = RetrievalManager(vector_store)

    def get_retrieval_sources(self, source_config: SourceConfig) -> list[RetrievalSource]:
        """Get retrieval sources"""
        retrieval_sources = []
        if source_config.web_search:
            retrieval_sources.append(RetrievalSource.WEB_SEARCH)
        if source_config.vector_store:
            retrieval_sources.append(RetrievalSource.VECTOR_STORE)
        return retrieval_sources

    async def process_message(
        self,
        message: str,
        session_id: str,
        history: list[ChatMessage] = None,
        source_config: SourceConfig = None,
        think_mode: bool = False,
    ) -> ChatResponse:
        """Process a chat message and return response"""
        try:
            # Set default source config if not provided
            if source_config is None:
                source_config = SourceConfig()

            sources = []
            context = ""

            retrieval_sources = self.get_retrieval_sources(source_config)
            # Use enhanced retrieval system if web search is enabled
            if retrieval_sources:
                # Create retrieval request
                retrieval_request = RetrievalRequest(
                    query=message,
                    sources=retrieval_sources,
                    max_results=settings.SEARCH_TOP_K,
                    min_score=settings.MIN_RELEVANCE_SCORE,
                )

                # Perform retrieval
                retrieval_response = await self.retrieval_manager.retrieve(retrieval_request)

                # Process retrieval results
                if retrieval_response.results:
                    # Apply reranking to all results combined
                    all_results = retrieval_response.results
                    if len(all_results) > 1:
                        # Convert to legacy format for reranker
                        legacy_results = []
                        for result in all_results:
                            legacy_result = type(
                                "Result",
                                (),
                                {
                                    "content": result.content,
                                    "score": result.score,
                                    "metadata": result.metadata,
                                },
                            )()
                            legacy_results.append(legacy_result)

                        # Rerank results
                        reranked_results = await self.reranker.rerank(message, legacy_results)

                        # Take top results after reranking
                        top_results = reranked_results[: settings.RERANK_TOP_K]
                    else:
                        top_results = all_results[: settings.RERANK_TOP_K]

                    # Build context and sources
                    for result in top_results:
                        if hasattr(result, "content"):  # Reranked result
                            content = result.content
                            metadata = result.metadata
                            score = result.score
                        else:  # Original retrieval result
                            content = result.content
                            metadata = result.metadata
                            score = result.score

                        context += f"\n---\n来源: {result.source if hasattr(result, 'source') else '知识库'}\n{content}\n"

                        sources.append(
                            {
                                "content": content[:200] + "...",
                                "title": (
                                    result.title
                                    if hasattr(result, "title")
                                    else metadata.get("document_name", "Unknown")
                                ),
                                "url": result.url if hasattr(result, "url") else None,
                                "source": (
                                    result.source if hasattr(
                                        result, "source") else "knowledge_base"
                                ),
                                "score": score,
                            }
                        )

                # Build prompt with context
                prompt = self._build_prompt_with_context(
                    message, context, history)
            else:
                prompt = self._build_prompt_without_context(message, history)

            # Get response from LLM
            response = await self.client.chat.completions.create(
                model=settings.LLM_THINK_MODEL if think_mode else settings.LLM_MODEL,
                messages=prompt,
                temperature=0.7,
                max_tokens=2000,
            )

            answer = response.choices[0].message.content

            return ChatResponse(
                message=answer,
                sources=sources,
                session_id=session_id,
                timestamp=datetime.now(),
            )

        except Exception as e:
            logger.error(f"Failed to process message: {e}")
            raise

    async def stream_message(
        self,
        message: str,
        session_id: str,
        history: list[ChatMessage] = None,
        source_config: SourceConfig = None,
        think_mode: bool = False,
    ) -> AsyncGenerator[str, None]:
        """Stream chat response"""
        try:
            # Set default source config if not provided
            if source_config is None:
                source_config = SourceConfig()

            prompt = self._build_prompt_without_context(message, history)

            # Stream response from LLM
            stream = await self.client.chat.completions.create(
                model=settings.LLM_THINK_MODEL if think_mode else settings.LLM_MODEL,
                messages=prompt,
                stream=True,
            )

            # Stream answer chunks
            async for chunk in stream:
                if think_mode and chunk.choices[0].delta.reasoning_content:
                    yield f"data: {json.dumps({'type': 'reasoning', 'data': chunk.choices[0].delta.reasoning_content})}\n\n"
                elif chunk.choices[0].delta.content:
                    yield f"data: {json.dumps({'type': 'content', 'data': chunk.choices[0].delta.content})}\n\n"

            # Send done signal
            yield f"data: {json.dumps({'type': 'done'})}\n\n"

        except Exception as e:
            logger.error(f"Failed to stream message: {e}")
            yield f"data: {json.dumps({'type': 'error', 'data': str(e)})}\n\n"

    def _build_prompt_with_context(
        self,
        message: str,
        context: str,
        history: list[ChatMessage] | None = None,
    ) -> list[dict]:
        """Build prompt for LLM with context"""
        system_prompt = """你是一个智能文档问答助手。你的任务是基于提供的文档内容回答用户的问题。

规则：
1. 如果文档中包含相关信息，请基于文档内容回答，并指出信息来源
2. 如果文档中没有相关信息，请诚实地告诉用户你无法从现有文档中找到答案
3. 保持回答简洁、准确、专业
4. 使用中文回答"""

        messages = [{"role": "system", "content": system_prompt}]

        # Add history if available
        if history:
            for msg in history[-5:]:  # Keep last 5 messages for context
                messages.append({"role": msg.role, "content": msg.content})

        # Add context and current message
        if context:
            user_prompt = f"""基于以下文档内容回答问题：

文档内容：
{context}

用户问题：{message}

请提供准确的回答。"""
        else:
            user_prompt = message

        messages.append({"role": "user", "content": user_prompt})

        return messages

    def _build_prompt_without_context(
        self,
        message: str,
        history: list[ChatMessage] | None = None,
    ) -> list[dict]:
        """Build prompt for LLM without context"""
        system_prompt = """You are a helpful assistant."""
        messages = [{"role": "system", "content": system_prompt}]

        # Add history if available
        if history:
            for msg in history[-5:]:  # Keep last 5 messages for context
                messages.append({"role": msg.role, "content": msg.content})

        messages.append({"role": "user", "content": message})
        return messages
