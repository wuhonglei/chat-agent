"""Web search retriever using Tavily Search"""

from loguru import logger
from tavily import AsyncTavilyClient

from app.models.retrieval import (
    RetrievalRequest,
    RetrievalResult,
    RetrievalSource,
)
from app.services.retrievers.base import BaseRetriever


class WebSearchRetriever(BaseRetriever):
    """Retriever for web search using Tavily"""

    def __init__(self, api_key: str):
        super().__init__("WebSearch")
        self.api_key = api_key
        self.client = None
        self.initialize()

    def initialize(self):
        """Initialize the Tavily Client"""
        self.client = AsyncTavilyClient(api_key=self.api_key)
        logger.info("Tavily Client initialized")

    async def retrieve(self, request: RetrievalRequest) -> list[RetrievalResult]:
        """Retrieve from web search"""
        try:
            # Use async Tavily client directly
            response = await self.client.search(
                query=request.query,
                search_depth="advanced",
                # Tavily max is typically 10
                max_results=min(request.max_results, 10),
                include_answer=False,
                include_raw_content=False,
                auto_parameters=True
            )

            results = []

            # Add answer if available
            if response.get("answer"):
                answer_result = RetrievalResult(
                    content=response["answer"],
                    title="Web Search Answer",
                    source=RetrievalSource.WEB_SEARCH,
                    score=1.0,  # High score for direct answers
                    metadata={
                        "type": "answer",
                        "search_engine": "tavily",
                        "query": request.query,
                    },
                )
                results.append(answer_result)

            # Process search results
            for result in response.get("results", []):
                score = result.get("score", 0.0)
                if score >= request.min_score:
                    retrieval_result = RetrievalResult(
                        content=result.get("content", ""),
                        title=result.get("title", ""),
                        url=result.get("url", ""),
                        source=RetrievalSource.WEB_SEARCH,
                        score=score,
                        metadata={
                            "published_date": result.get("published_date"),
                            "raw_content": result.get("raw_content", ""),
                            "search_engine": "tavily",
                            **result,
                        },
                    )
                    results.append(retrieval_result)

            logger.info(
                f"Web search retrieved {len(results)} results for query: {request.query}")
            return results

        except Exception as e:
            logger.error(f"Web search retrieval failed: {e}")
            return []

    async def health_check(self) -> bool:
        """Check Tavily API health"""
        try:
            # Use async Tavily client directly
            response = await self.client.search(
                query="test", search_depth="basic", max_results=1
            )
            return "results" in response
        except Exception as e:
            logger.error(f"Web search health check failed: {e}")
            return False
