"""组件 Schema 服务，负责获取和缓存组件的 JSON Schema"""
import json
import httpx
from app.core.config import settings
from app.utils.logger import logger


class ComponentSchemaService:
    """组件 Schema 服务类，负责获取和缓存组件的 JSON Schema"""

    # 类变量，用于应用级别的缓存
    _schema_cache: dict[str, dict] = {}

    def __init__(
        self,
        base_url: str = settings.component_schema_api_url,
        timeout: int = 5,
        max_retries: int = 2,
    ):
        """
        初始化 ComponentSchemaService

        Args:
            base_url: Schema API 基础地址
            timeout: 请求超时时间（秒）
            max_retries: 最大重试次数
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.max_retries = max_retries

    async def get_schema(self, component_tool_name: str) -> dict:
        """
        获取单个组件的 Schema（带缓存检查）

        Args:
            component_tool_name: 组件工具名称，例如 'weather'

        Returns:
            组件的 JSON Schema 字典

        Raises:
            Exception: 当获取 Schema 失败时抛出异常
        """
        # 先检查缓存
        if component_tool_name in self._schema_cache:
            logger.debug(
                "Schema cache hit",
                component_tool_name=component_tool_name,
            )
            return self._schema_cache[component_tool_name]

        # 缓存未命中，从 API 获取
        logger.info(
            "Fetching schema from API",
            component_tool_name=component_tool_name,
        )
        schema = await self._fetch_schema_from_api(component_tool_name)

        # 更新缓存
        self._schema_cache[component_tool_name] = schema
        logger.info(
            "Schema cached",
            component_tool_name=component_tool_name,
        )

        return schema

    async def get_schemas(self, component_tool_names: list[str]) -> dict[str, dict]:
        """
        批量获取多个组件的 Schema

        Args:
            component_tool_names: 组件工具名称列表

        Returns:
            字典，键为组件工具名称，值为对应的 JSON Schema
        """
        if not component_tool_names:
            return {}

        # 并行获取所有 Schema
        import asyncio
        tasks = [self.get_schema(name) for name in component_tool_names]
        schemas = await asyncio.gather(*tasks, return_exceptions=True)

        result = {}
        for name, schema in zip(component_tool_names, schemas):
            if isinstance(schema, Exception):
                logger.error(
                    "Failed to get schema",
                    component_tool_name=name,
                    error=schema,
                )
                # 跳过失败的 Schema，不添加到结果中
                continue
            result[name] = schema

        return result

    async def _fetch_schema_from_api(self, component_tool_name: str) -> dict:
        """
        从 API 获取 Schema（私有方法）

        Args:
            component_tool_name: 组件工具名称

        Returns:
            组件的 JSON Schema 字典

        Raises:
            httpx.HTTPError: 当 HTTP 请求失败时
            json.JSONDecodeError: 当 JSON 解析失败时
        """
        url = f"{self.base_url}/{component_tool_name}.json"

        last_exception = None
        for attempt in range(self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.get(url)
                    response.raise_for_status()

                    schema = response.json()
                    logger.info(
                        "Schema fetched successfully",
                        component_tool_name=component_tool_name,
                        url=url,
                        attempt=attempt + 1,
                    )
                    return schema

            except httpx.TimeoutException as e:
                last_exception = e
                logger.warning(
                    "Schema fetch timeout",
                    component_tool_name=component_tool_name,
                    url=url,
                    attempt=attempt + 1,
                    max_retries=self.max_retries,
                )
                if attempt < self.max_retries:
                    continue

            except httpx.HTTPStatusError as e:
                last_exception = e
                logger.error(
                    "Schema fetch HTTP error",
                    component_tool_name=component_tool_name,
                    url=url,
                    status_code=e.response.status_code,
                    attempt=attempt + 1,
                )
                # HTTP 错误不重试（如 404、500 等）
                raise

            except httpx.RequestError as e:
                last_exception = e
                logger.warning(
                    "Schema fetch request error",
                    component_tool_name=component_tool_name,
                    url=url,
                    attempt=attempt + 1,
                    max_retries=self.max_retries,
                    error=str(e),
                )
                if attempt < self.max_retries:
                    continue

            except json.JSONDecodeError as e:
                last_exception = e
                logger.error(
                    "Schema JSON decode error",
                    component_tool_name=component_tool_name,
                    url=url,
                    error=str(e),
                )
                # JSON 解析错误不重试
                raise

        # 所有重试都失败
        logger.error(
            "Schema fetch failed after retries",
            component_tool_name=component_tool_name,
            url=url,
            max_retries=self.max_retries,
            error=last_exception,
        )
        raise last_exception

    @classmethod
    def clear_cache(cls):
        """清空缓存（用于测试或强制刷新）"""
        cls._schema_cache.clear()
        logger.info("Schema cache cleared")
