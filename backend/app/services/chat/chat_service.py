"""Chat service facade for the streaming chat pipeline."""

from collections.abc import AsyncGenerator
from typing import Literal

from app.agents import ChatSessionAgent, TitleGenerationAgent
from app.core.config import settings
from app.mcp.client import MCPClientManager
from app.schemas.chat import ChatRequest
from app.schemas.config import ChatContextConfig, LLMConfig
from app.schemas.user import MemoryListItem, MemorySearchItem
from app.services.base_service.embedding_service import EmbeddingService
from app.services.base_service.model_resolver import resolve_scenario
from app.services.chat.chat_orchestrator import ChatOrchestrator
from app.services.chat.history_context_service import HistoryContextService
from app.services.chat.kb_rag_context_service import KbRagContextService
from app.services.chat.post_process_service import PostProcessService
from app.services.user.memory_service import MemoryService
from app.utils.date import get_relative_time_diff
from app.utils.token import TokenCalculator


class ChatService:
    """Assemble collaborators for the chat streaming entrypoint."""

    def __init__(
        self,
        think_mode: bool,
        llm_config: LLMConfig,
        mcp_manager: MCPClientManager,
        chat_context_config: ChatContextConfig,
    ):
        self.chat_context_config = chat_context_config
        self.memory_config = self.chat_context_config.memory_config
        self.memory_service = MemoryService(self.memory_config)
        token_calculator = TokenCalculator(
            llm_config.model_name, llm_config.context_limit
        )

        self.history_context_service = HistoryContextService(
            chat_context_config=chat_context_config,
            token_calculator=token_calculator,
        )
        self.chat_session_agent = ChatSessionAgent(
            think_mode=think_mode,
            llm_config=llm_config,
            mcp_manager=mcp_manager,
            history_context_service=self.history_context_service,
            chat_context_config=chat_context_config,
        )
        title_llm_config = resolve_scenario("title_generation")
        self.title_generation_agent = TitleGenerationAgent(
            think_mode=False, llm_config=title_llm_config
        )
        self.post_process_service = PostProcessService(self.memory_service)
        self.kb_rag_context_service = KbRagContextService(
            rag_config=settings.kb_file_rag,
            embedding_service=EmbeddingService(settings.embedding_model),
        )
        self.chat_orchestrator = ChatOrchestrator(
            chat_session_agent=self.chat_session_agent,
            title_generation_agent=self.title_generation_agent,
            history_context_service=self.history_context_service,
            post_process_service=self.post_process_service,
            kb_rag_context_service=self.kb_rag_context_service,
        )

    @staticmethod
    def _score_to_relevance(score: float | None) -> Literal["高", "中", "低"]:
        if score is None:
            return "低"
        if score >= 0.8:
            return "高"
        if score >= 0.5:
            return "中"
        return "低"

    @staticmethod
    def _is_simple_ack_query(query: str) -> bool:
        normalized_query = query.strip().lower()
        if not normalized_query:
            return True

        normalized_query = normalized_query.strip("，。！？、,.!?~～…")
        simple_ack_phrases = {
            "好",
            "好的",
            "ok",
            "okay",
            "继续",
            "确认",
            "可以",
            "收到",
            "行",
            "没问题",
            "明白",
        }
        return normalized_query in simple_ack_phrases

    async def _search_user_memories(
        self, *, query: str, user_id: str
    ) -> list[MemorySearchItem]:
        if self._is_simple_ack_query(query):
            return []
        searched_memories: list[MemoryListItem] = await self.memory_service.search(
            query=query,
            user_id=user_id,
            threshold=self.memory_config.search_threshold,
        )
        return [
            MemorySearchItem(
                id=memory.id,
                memory=memory.memory,
                hash=memory.hash,
                metadata=memory.metadata,
                created_at=get_relative_time_diff(memory.created_at),
                relevance=self._score_to_relevance(memory.score),
            )
            for memory in searched_memories
        ]

    async def stream_chat_events(
        self,
        chat_request: ChatRequest,
        user_message_id: str,
        assistant_message_id: str,
        user_id: str,
    ) -> AsyncGenerator[str, None]:
        async for event in self.chat_orchestrator.run_chat_turn(
            chat_request=chat_request,
            user_message_id=user_message_id,
            assistant_message_id=assistant_message_id,
            user_id=user_id,
            memory_search=self._search_user_memories,
        ):
            yield event
