"""Chat service for RAG-based Q&A"""

import json
from collections.abc import AsyncGenerator
from datetime import datetime

from loguru import logger
from openai import AsyncOpenAI

from app.core.config import settings
from app.models.chat import ChatMessage, ChatResponse, ChatSource, SourceConfig
from app.models.retrieval import RetrievalRequest, RetrievalSource
from app.services.retrieval_manager import RetrievalManager
from app.utils.common import exclude_fields
from app.mcp.mcp_client import MCPClientManager


class ChatService:
    """Handle chat interactions with RAG"""

    def __init__(self, mcp_manager: MCPClientManager):
        self.client = AsyncOpenAI(
            api_key=settings.LLM_API_KEY,
            base_url=settings.LLM_API_BASE,
        )
        self.retrieval_manager = RetrievalManager()
        self.mcp_manager = mcp_manager

    def get_retrieval_sources(self, source_config: SourceConfig) -> list[RetrievalSource]:
        """Get retrieval sources"""
        retrieval_sources = []
        if source_config.web_search:
            retrieval_sources.append(RetrievalSource.WEB_SEARCH)
        if source_config.confluence:
            retrieval_sources.append(RetrievalSource.CONFLUENCE)
        if source_config.google_docs:
            retrieval_sources.append(RetrievalSource.GOOGLE_DOCS)
        if source_config.knowledge_base:
            retrieval_sources.append(RetrievalSource.KNOWLEDGE_BASE)
        return retrieval_sources

    def _has_enabled_sources(self, source_config: SourceConfig) -> bool:
        """Check if source_config has any enabled sources"""
        config_dict = source_config.model_dump()
        return any(value is True for value in config_dict.values())

    async def _call_llm_with_tools(
        self,
        messages: list[dict],
        model: str,
        tools: list[dict],
    ) -> tuple[str, list[ChatSource]]:
        """Call LLM with MCP tools and handle tool calls"""
        sources: list[ChatSource] = []
        max_iterations = 5  # Prevent infinite loops

        for _ in range(max_iterations):
            # Call LLM with tools
            response = await self.client.chat.completions.create(
                model=model,
                messages=messages,
                tools=tools if tools else None,
                stream=False,
            )

            assistant_message = response.choices[0].message

            # If no tool calls, return the response
            if not assistant_message.tool_calls:
                return assistant_message.content or "", sources

            # Add assistant message to conversation
            messages.append({
                "role": "assistant",
                "content": assistant_message.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": tc.type,
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments
                        }
                    }
                    for tc in assistant_message.tool_calls
                ]
            })

            # Execute tool calls
            for tool_call in assistant_message.tool_calls:
                tool_name = tool_call.function.name
                try:
                    # Parse arguments
                    arguments = json.loads(tool_call.function.arguments)

                    # Call the tool via MCP manager
                    logger.info(
                        f"Calling MCP tool: {tool_name} with args: {arguments}")
                    result = await self.mcp_manager.call_tool(tool_name, arguments)

                    # Add tool result to messages
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": str(result)
                    })

                    # Add to sources if applicable
                    sources.append(ChatSource(
                        content=str(result)[
                            :200] + "..." if len(str(result)) > 200 else str(result),
                        title=f"MCP Tool: {tool_name}",
                        url=None,
                        source="mcp_tool",
                        score=1.0,
                        metadata={"tool_name": tool_name,
                                  "arguments": arguments}
                    ))

                except Exception as e:
                    logger.error(f"Failed to call tool {tool_name}: {e}")
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": f"Error calling tool: {str(e)}"
                    })

        # If we hit max iterations, return last response
        return "Maximum tool call iterations reached. Please try rephrasing your question.", sources

    async def _perform_retrieval(
        self, message: str, source_config: SourceConfig
    ) -> tuple[str, list[ChatSource]]:
        """Perform retrieval and return context and sources"""
        sources: list[ChatSource] = []
        context = ""

        retrieval_sources = self.get_retrieval_sources(source_config)

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
                # Results are already reranked by RetrievalManager
                top_results = retrieval_response.results

                # Build context and sources with numbered references
                for i, result in enumerate(top_results, 1):
                    content = result.content
                    score = result.score

                    # Format source info for better citation
                    source_info = f"[^CITE:{i}] {result.title or result.source}"
                    if result.url:
                        source_info += f" ({result.url})"

                    context += f"\n---\n{source_info}\n{content}\n"

                    sources.append(
                        ChatSource(**{
                            "content": result.metadata.get("snippet") or content[:200] + "...",
                            "title": result.title,
                            "url": result.url,
                            "source": result.source,
                            "score": score,
                            "favicon": result.metadata.get("favicon"),
                            "metadata": exclude_fields(result.metadata, ["favicon", "snippet"])
                        })
                    )

        return context, sources

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

            # Choose between retrieval and MCP tool calling
            model = settings.LLM_THINK_MODEL if think_mode else settings.LLM_MODEL

            if self._has_enabled_sources(source_config):
                # Use retrieval if any source is enabled in config
                context, sources = await self._perform_retrieval(message, source_config)

                # Build prompt based on whether context is available
                if context:
                    prompt = self._build_prompt_with_context(
                        message, context, history)
                else:
                    prompt = self._build_prompt_without_context(
                        message, history)

                # Get response from LLM
                response = await self.client.chat.completions.create(
                    model=model,
                    messages=prompt,
                    stream=False,
                )

                answer = response.choices[0].message.content
            else:
                # Use MCP tools - let LLM decide whether to call tools
                prompt = self._build_prompt_without_context(message, history)

                # Get MCP tools for LLM
                tools = await self.mcp_manager.get_tools_for_llm() if self.mcp_manager and self.mcp_manager._initialized else []

                # Call LLM with tools
                answer, sources = await self._call_llm_with_tools(prompt, model, tools)

            return ChatResponse(
                message=answer,
                sources=sources,
                session_id=session_id,
                timestamp=datetime.now(),
            )

        except Exception as e:
            logger.error(f"Failed to process message: {e}")
            raise

    @staticmethod
    def _format_sse_message(msg_type: str, data=None) -> str:
        """Format SSE (Server-Sent Events) message"""
        if data is None:
            return f"data: {json.dumps({'type': msg_type})}\n\n"
        return f"data: {json.dumps({'type': msg_type, 'data': data}, ensure_ascii=False)}\n\n"

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

            # Choose between retrieval and MCP tool calling
            model = settings.LLM_THINK_MODEL if think_mode else settings.LLM_MODEL
            sources: list[ChatSource] = []

            if self._has_enabled_sources(source_config):
                # Use retrieval if any source is enabled in config
                context, sources = await self._perform_retrieval(message, source_config)

                # Build prompt based on whether context is available
                if context:
                    prompt = self._build_prompt_with_context(
                        message, context, history)
                else:
                    prompt = self._build_prompt_without_context(
                        message, history)

                if sources:
                    # Convert ChatSource objects to dictionaries for JSON serialization
                    sources_dict = [source.model_dump() for source in sources]
                    yield self._format_sse_message('sources', sources_dict)

                # Stream response from LLM
                stream = await self.client.chat.completions.create(
                    model=model,
                    messages=prompt,
                    stream=True,
                )

                # Stream answer chunks
                async for chunk in stream:
                    if think_mode and chunk.choices[0].delta.reasoning_content:
                        yield self._format_sse_message('reasoning', chunk.choices[0].delta.reasoning_content)
                    elif chunk.choices[0].delta.content:
                        yield self._format_sse_message('content', chunk.choices[0].delta.content)
            else:
                # Use MCP tools - let LLM decide whether to call tools
                prompt = self._build_prompt_without_context(message, history)

                # Get MCP tools for LLM
                tools = await self.mcp_manager.get_tools_for_llm() if self.mcp_manager and self.mcp_manager._initialized else []

                # For streaming with tools, we need to handle it differently
                # First call without streaming to handle tool calls
                answer, tool_sources = await self._call_llm_with_tools(prompt, model, tools)

                if tool_sources:
                    sources_dict = [source.model_dump()
                                    for source in tool_sources]
                    yield self._format_sse_message('sources', sources_dict)

                # Stream the final answer
                yield self._format_sse_message('content', answer)

            # Send done signal
            yield self._format_sse_message('done')

        except Exception as e:
            logger.error(f"Failed to stream message: {e}")
            yield self._format_sse_message('error', str(e))

    def _build_prompt_with_context(
        self,
        message: str,
        context: str,
        history: list[ChatMessage] | None = None,
    ) -> list[dict]:
        """Build prompt for LLM with context"""
        system_prompt = """你是一个智能问答助手。你的任务是基于提供的参考资料回答用户的问题。

规则：
1. 仔细分析提供的参考资料，这些资料可能来自知识库文档或实时网络搜索
2. 如果是网络搜索结果，请注意信息的时效性和来源可靠性
3. 在回答中必须使用引用标记 [^CITE:n] 来标注信息来源，其中 n 是参考资料的编号
4. 当引用某个来源的信息时，在相关内容后添加 [^CITE:n] 格式的引用标记
5. 如果综合多个来源，请分别标注各自的引用编号，如 [^CITE:1][^CITE:2]
6. 如果参考资料中没有相关信息，请诚实告知用户，并根据你的知识提供可能的建议
7. 保持回答准确、专业、有条理
8. 优先使用参考资料中的信息，确保答案的准确性

引用示例：
根据资料显示，Python 是一种高级编程语言[^CITE:1]，它具有简洁易读的语法特点[^CITE:2]。"""

        messages = [{"role": "system", "content": system_prompt}]

        # Add history if available
        if history:
            for msg in history[-5:]:  # Keep last 5 messages for context
                messages.append({"role": msg.role, "content": msg.content})

        # Add context and current message
        if context:
            user_prompt = f"""基于以下参考资料回答问题：

参考资料（每个资料都有编号 [^CITE:n]，请在回答中使用这些编号来引用）：
{context}

用户问题：{message}

请基于上述参考资料提供准确、详细的回答。在回答中必须使用 [^CITE:n] 格式引用相应的参考资料。如果参考资料中包含多个来源，请综合各个来源的信息并分别标注引用。"""
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
