"""Chat service for RAG-based Q&A"""

import json
from datetime import datetime
from typing import AsyncGenerator, List, Optional

from loguru import logger
from openai import AsyncOpenAI

from app.core.config import settings
from app.core.vector_store import VectorStore
from app.models.chat import ChatMessage, ChatResponse
from app.services.reranker import Reranker


class ChatService:
    """Handle chat interactions with RAG"""

    def __init__(self, vector_store: VectorStore):
        self.vector_store = vector_store
        self.client = AsyncOpenAI(
            api_key=settings.LLM_API_KEY,
            base_url=settings.LLM_API_BASE,
        )
        self.reranker = Reranker()

    async def process_message(
        self,
        message: str,
        session_id: str,
        history: List[ChatMessage] = None,
        use_knowledge_base: bool = True,
        think_mode: bool = False,
    ) -> ChatResponse:
        """Process a chat message and return response"""
        try:
            # Search knowledge base if enabled
            sources = []
            context = ""

            if use_knowledge_base:
                # Search for relevant documents
                search_results = await self.vector_store.search(
                    message, top_k=settings.SEARCH_TOP_K
                )

                # Rerank results
                if search_results:
                    search_results = await self.reranker.rerank(message, search_results)

                    # Build context from top results
                    for result in search_results[: settings.RERANK_TOP_K]:
                        context += f"\n---\n{result.content}\n"
                        sources.append(
                            {
                                "content": result.content[:200] + "...",
                                "document_name": result.metadata.get("document_name", "Unknown"),
                                "score": result.score,
                            }
                        )

                # Build prompt
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
        history: List[ChatMessage] = None,
        use_knowledge_base: bool = True,
        think_mode: bool = False,
    ) -> AsyncGenerator[str, None]:
        """Stream chat response"""
        try:
            # Search knowledge base if enabled
            context = ""
            sources = []

            if use_knowledge_base:
                # Search for relevant documents
                search_results = await self.vector_store.search(
                    message, top_k=settings.SEARCH_TOP_K
                )

                # Rerank results
                if search_results:
                    search_results = await self.reranker.rerank(message, search_results)

                    # Build context from top results
                    for result in search_results[: settings.RERANK_TOP_K]:
                        context += f"\n---\n{result.content}\n"
                        sources.append(
                            {
                                "content": result.content[:200] + "...",
                                "document_name": result.metadata.get("document_name", "Unknown"),
                                "score": result.score,
                            }
                        )

                # Build prompt
                prompt = self._build_prompt_with_context(
                    message, context, history)
            else:
                prompt = self._build_prompt_without_context(message, history)

            # Stream response from LLM
            stream = await self.client.chat.completions.create(
                model=settings.LLM_THINK_MODEL if think_mode else settings.LLM_MODEL,
                messages=prompt,
                stream=True,
            )

            # First, send sources
            if sources:
                yield f"data: {json.dumps({'type': 'sources', 'data': sources})}\n\n"

            # Stream answer chunks
            async for chunk in stream:
                logger.info(f"Stream chunk: {chunk}")
                if chunk.choices[0].delta.content:
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
        history: Optional[List[ChatMessage]] = None,
    ) -> List[dict]:
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
        history: Optional[List[ChatMessage]] = None,
    ) -> List[dict]:
        """Build prompt for LLM without context"""
        system_prompt = """You are a helpful assistant.
        """
        messages = [{"role": "system", "content": system_prompt}]

        # Add history if available
        if history:
            for msg in history[-5:]:  # Keep last 5 messages for context
                messages.append({"role": msg.role, "content": msg.content})

        messages.append({"role": "user", "content": message})
        return messages
