"""Confluence search retriever"""

import asyncio
from re import search
from atlassian import Confluence
from loguru import logger
from openai import AsyncOpenAI

from app.models.retrieval import (
    RetrievalRequest,
    RetrievalResult,
    RetrievalSource,
    ConfluenceMetadata,
)
from app.core.config import settings
from app.services.retrievers.base import BaseRetriever
from app.services.retrievers.utils import BasePreprocessor
from app.utils.common import remove_leading_whitespace
from app.models.confluence import ConfluencePageDetail, ConfluenceCQLSearchResponse
from app.models.document import Document, DocumentSource


class ConfluenceRetriever(BaseRetriever):
    """Retriever for Confluence"""

    def __init__(self, api_config: dict):
        super().__init__("Confluence")
        self.api_config = api_config
        self.client = None
        self.llm_client = None
        # 并发控制参数
        self.max_concurrent_requests = 10  # 最大并发请求数
        self.page_timeout = 30  # 单个页面获取超时时间（秒）
        self.preprocessor = BasePreprocessor(
            base_url=self.api_config["url"],
        )
        self.base_url = self.api_config["url"].rstrip('/')
        self.initialize()

    def initialize(self):
        """Initialize the Confluence Client"""
        self.client = Confluence(
            url=self.api_config["url"],
            token=self.api_config["token"],
            cloud=False,
        )
        self.llm_client = AsyncOpenAI(
            api_key=settings.LLM_API_KEY,
            base_url=settings.LLM_API_BASE,
        )
        logger.info("Confluence Client initialized")

    async def query_to_keywords(self, query: str) -> str:
        """Convert a query to a list of keywords"""
        system_prompt = remove_leading_whitespace("""You are a helpful assistant that converts a query to a list of keywords.
        Examples:
        Query: How to use the confluence API?
        Keywords: confluence, api

        Query: I want to query the ai agent framework?
        Keywords: ai agent, framework

        1. The keywords should be concise and relevant to the query.
        2. The keywords should be separated by commas.
        """)
        user_prompt = remove_leading_whitespace(f"""Query: {query}
        Keywords:
        """)
        response = await self.llm_client.chat.completions.create(
            model=settings.LLM_MODEL,
            messages=[{"role": "system", "content": system_prompt}, {
                "role": "user", "content": user_prompt}],
        )
        return response.choices[0].message.content.strip()

    def post_process_keywords(self, content: str) -> str:
        """Post process the keywords"""
        # 移除可能的前置 "Keywords:" 文本
        prefix = "Keywords:"
        if content.lower().startswith(prefix):
            content = content[len(prefix):].strip()  # 移除 "Keywords:" 及其后的空格

        # 按逗号分割并清理每个关键词
        keywords = [keyword.strip()
                    for keyword in content.split(",") if keyword.strip()]
        return ' '.join(keywords)

    async def _get_page_content(self, page_id: str, timeout: int = 30) -> ConfluencePageDetail | None:
        """异步获取单个页面的内容，带超时控制"""
        try:
            # 使用 asyncio.to_thread 将同步的 Confluence API 调用包装为异步
            # 并添加超时控制
            full_page_dict = await asyncio.wait_for(
                asyncio.to_thread(
                    self.client.get_page_by_id,
                    page_id,
                    expand='body.storage,version,history.lastUpdated'
                ),
                timeout=timeout
            )
            # 将字典转换为 ConfluencePageDetail 实例
            return ConfluencePageDetail(**full_page_dict)
        except asyncio.TimeoutError:
            logger.warning(f"Timeout getting page {page_id} after {timeout}s")
            return None
        except Exception as e:
            logger.error(f"Failed to get page {page_id}: {e}")
            return None

    def get_page_ids(self, search_results: ConfluenceCQLSearchResponse) -> list[str]:
        """Get page IDs from search results"""
        # Parse search results into typed model
        try:
            cql_response = search_results
            if not cql_response.results:
                return []
            return [result.content.id for result in cql_response.results if result.content.id]
        except Exception as e:
            logger.warning(
                f"Failed to parse CQL response, falling back to dict access: {e}")
            return []

    async def _fetch_pages_concurrently(self, page_ids: list[str]) -> list[ConfluencePageDetail | Exception | None]:
        """并发获取多个页面的内容"""
        logger.info(
            f"Fetching {len(page_ids)} pages concurrently (max {self.max_concurrent_requests})")

        # 使用信号量控制并发数量
        semaphore = asyncio.Semaphore(self.max_concurrent_requests)

        async def get_page_with_semaphore(page_id: str):
            async with semaphore:
                return await self._get_page_content(page_id, self.page_timeout)

        # 创建所有任务并并发执行
        page_tasks = [get_page_with_semaphore(page_id) for page_id in page_ids]
        return await asyncio.gather(*page_tasks, return_exceptions=True)

    def _extract_page_content(self, page_detail: ConfluencePageDetail) -> str:
        """从页面内容中提取文本"""
        try:
            # 从 Confluence 页面内容中提取文本
            body = page_detail.body.storage.value
            processed_html, processed_markdown = self.preprocessor.process_html_content(
                html_content=body,
                page_id=page_detail.id,
                confluence_client=self.client,
            )

            return processed_markdown
        except Exception as e:
            logger.warning(f"Failed to extract content from page: {e}")
            return ""

    def _process_page_results(self, page_details: list[ConfluencePageDetail | Exception | None], page_ids: list[str]) -> tuple[list[Document], dict]:
        """处理页面获取结果并生成检索结果"""
        documents: list[Document] = []
        stats = {"success": 0, "error": 0, "timeout": 0}

        for i, page_detail in enumerate(page_details):
            page_id = page_ids[i]

            # 处理异常情况
            if isinstance(page_detail, Exception):
                stats["error"] += 1
                if isinstance(page_detail, asyncio.TimeoutError):
                    stats["timeout"] += 1
                    logger.warning(f"Timeout getting page {page_id}")
                else:
                    logger.error(
                        f"Failed to get page {page_id}: {page_detail}")
                continue

            if page_detail is None:
                stats["error"] += 1
                continue

            stats["success"] += 1

            # 提取页面内容
            markdown = self._extract_page_content(page_detail)
            # 组装完整的URL
            webui_path = page_detail.links.webui if page_detail.links else ''
            source_url = f"{self.base_url}{webui_path}" if webui_path else ''

            # 提取最后修改时间和修改人信息
            last_modified_time = page_detail.get_last_modified_time()
            last_modifier_name = page_detail.get_last_modifier_name()

            document = Document(
                content=markdown,
                id=page_id,
                name=page_detail.title,
                source=DocumentSource.CONFLUENCE,
                source_url=source_url,
                metadata={
                    "last_modified_time": last_modified_time,
                    "last_modifier_name": last_modifier_name,
                }
            )
            documents.append(document)

        return documents, stats

    async def retrieve(self, request: RetrievalRequest) -> list[RetrievalResult]:
        """Retrieve from Confluence"""
        try:
            # 1. 生成关键词
            keywords_res = await self.query_to_keywords(request.query)
            keywords = self.post_process_keywords(keywords_res)
            logger.info(f"query:{request.query}, keywords:{keywords}")

            # 2. 搜索页面
            search_results_dict = self.client.cql(
                f"""siteSearch ~ "{keywords}" """, limit=request.max_results)
            search_results = ConfluenceCQLSearchResponse(**search_results_dict)
            page_ids = self.get_page_ids(search_results)
            id_to_result = search_results.id_to_result

            if not page_ids:
                logger.info("No valid page IDs found")
                return []

            # 3. 获取页面内容
            page_details = await self._fetch_pages_concurrently(page_ids)

            # 4. 处理文档并转换为检索结果
            documents, stats = self._process_page_results(
                page_details, page_ids)

            # 5. 直接转换为检索结果（不进行 embedding 排序）
            final_results = []
            for i, document in enumerate(documents, 1):
                # 构建类型化的 Confluence metadata
                confluence_metadata = ConfluenceMetadata(
                    document_id=document.id,
                    snippet=id_to_result[document.id].snippet,
                    **document.metadata,
                )

                # 使用 CQL 的原始顺序
                final_results.append(RetrievalResult(
                    content=document.content,
                    title=document.name,
                    url=document.source_url,
                    source=RetrievalSource.CONFLUENCE,
                    score=1 / i,  # 倒排分数，将由 reranker 重新评分
                    metadata=confluence_metadata.model_dump(exclude_none=True),
                ))

            logger.info(
                f"Page retrieval completed: {stats['success']} success, "
                f"{stats['error']} errors, {stats['timeout']} timeouts"
            )

            # 返回所有结果，让 RetrievalManager 的 reranker 进行排序
            final_results.sort(key=lambda x: x.score, reverse=True)
            final_results = final_results[:request.max_results]
            return final_results

        except Exception as e:
            logger.error(f"Confluence retrieval failed: {e}")
            return []

    async def health_check(self) -> bool:
        """Check if the Confluence retriever is healthy"""
        try:
            await self.client.get_all_spaces(limit=1)
            return True
        except Exception as e:
            logger.error(f"Confluence health check failed: {e}")
            return False
