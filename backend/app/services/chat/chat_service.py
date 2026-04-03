"""Chat service facade for the streaming chat pipeline."""

from collections.abc import AsyncGenerator

from app.agents import ChatSessionAgent, TitleGenerationAgent
from app.core.config import settings
from app.mcp.mcp_client import MCPClientManager
from app.schemas.chat import ChatRequest
from app.schemas.config import ChatContextConfig
from app.schemas.user import MemoryListItem
from app.services.chat.chat_orchestrator import ChatOrchestrator
from app.services.chat.history_context_service import HistoryContextService
from app.services.chat.post_process_service import PostProcessService
from app.services.user.memory_service import MemoryService
from app.utils.token import TokenCalculator


class ChatService:
    """Assemble collaborators for the chat streaming entrypoint."""

    def __init__(
        self,
        think_mode: bool,
        mcp_manager: MCPClientManager,
        chat_context_config: ChatContextConfig,
    ):
        self.chat_context_config = chat_context_config
        self.memory_config = self.chat_context_config.memory_config
        self.memory_service = MemoryService(self.memory_config)
        token_calculator = TokenCalculator(settings.response_model.model_name)

        self.chat_session_agent = ChatSessionAgent(
            think_mode=think_mode,
            llm_config=settings.response_model,
            mcp_manager=mcp_manager,
        )
        self.title_generation_agent = TitleGenerationAgent(
            think_mode=False, llm_config=settings.tool_call_model
        )
        self.history_context_service = HistoryContextService(
            chat_context_config=chat_context_config,
            token_calculator=token_calculator,
        )
        self.post_process_service = PostProcessService(self.memory_service)
        self.orchestrator = ChatOrchestrator(
            chat_session_agent=self.chat_session_agent,
            title_generation_agent=self.title_generation_agent,
            history_context_service=self.history_context_service,
            post_process_service=self.post_process_service,
        )

    async def _search_memories(
        self, *, query: str, user_id: str
    ) -> list[MemoryListItem]:
        if not query:
            return []
        return await self.memory_service.search(
            query=query,
            user_id=user_id,
            threshold=self.memory_config.search_threshold,
        )

    async def stream_response(
        self,
        chat_request: ChatRequest,
        user_message_id: str,
        assistant_message_id: str,
        user_id: str,
    ) -> AsyncGenerator[str, None]:
        async for chunk in self.orchestrator.stream_response(
            chat_request=chat_request,
            user_message_id=user_message_id,
            assistant_message_id=assistant_message_id,
            user_id=user_id,
            memory_search=self._search_memories,
        ):
            yield chunk
