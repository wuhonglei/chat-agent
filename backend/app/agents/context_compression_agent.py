"""Context Compression Agent for compressing tool results and conversation context"""

from collections.abc import AsyncGenerator
from typing import Any, Dict, List, Literal, Optional
import time

from app.agents.base import BaseAgent
from app.schemas.config import LLMConfig
from app.schemas.token_stats import BaseTokenStats, TokenUsage
from app.utils.compression import (
    GenericCompressor,
    IterationCompressor,
    ContextMonitor,
    CompressionResult,
    ContentType
)
from app.utils.logger import logger
from app.utils.time import get_current_time, get_time_duration


class ContextCompressionAgent(BaseAgent):
    """Context Compression Agent - responsible for intelligently compressing tool results and conversation context"""

    def __init__(self, think_mode: bool, llm_config: LLMConfig, compression_config: Optional[Dict[str, Any]] = None):
        super().__init__(think_mode, llm_config)

        # Use provided config or default
        if compression_config:
            self.compression_config = compression_config
        else:
            # Import settings to get default config
            from app.core.config import settings
            self.compression_config = {
                'single_round': settings.compression.single_round,
                'iteration_compression': settings.compression.iteration_compression,
            }

        # Compressor components
        self.tool_result_compressor = ToolResultCompressor(
            llm_config, self.compression_config)
        self.iteration_compressor = IterationCompressor(
            max_context_length=self.compression_config['iteration_compression']['max_iteration_context_length']
        )
        self.context_monitor = ContextMonitor(llm_config.model_name)

        # Compression stats
        self.compression_stats = {
            'original_length': 0,
            'compressed_length': 0,
            'compression_ratio': 0.0,
            'processing_time': 0.0,
            'total_compressions': 0,
        }

    async def stream_execute(
        self,
        compression_type: Literal['tool_results', 'iteration', 'conversation'],
        input_data: Dict[str, Any],
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """
        Stream execute context compression

        Args:
            compression_type: Compression type ('tool_results', 'iteration', 'conversation')
            input_data: Compression input data
                - tool_results: Tool call results list
                - iteration: Iteration context data
                - conversation: Conversation history data
        """
        start_time = get_current_time()

        try:
            if compression_type == 'tool_results':
                async for result in self._compress_tool_results(input_data['results']):
                    yield self.format_sse_message('compression_progress', result)

            elif compression_type == 'iteration':
                async for result in self._compress_iteration_context(
                    input_data['current_results'],
                    input_data.get('historical_context', []),
                    input_data.get('iteration', 0)
                ):
                    yield self.format_sse_message('compression_progress', result)

            elif compression_type == 'conversation':
                async for result in self._compress_conversation_context(
                    input_data['history'],
                    input_data.get('current_query', '')
                ):
                    yield self.format_sse_message('compression_progress', result)

            else:
                logger.error("Unknown compression type",
                             compression_type=compression_type)
                yield self.format_sse_message('compression_error', {
                    'error': f'Unknown compression type: {compression_type}'
                })

            # Update compression stats
            processing_time = get_time_duration(start_time)
            self.compression_stats['processing_time'] = processing_time
            self.compression_stats['total_compressions'] += 1

            logger.info(
                "Context compression completed",
                compression_type=compression_type,
                processing_time=processing_time,
                compression_ratio=self.compression_stats.get(
                    'compression_ratio', 0.0)
            )

        except Exception as e:
            processing_time = get_time_duration(start_time)
            logger.error(
                "Context compression failed",
                compression_type=compression_type,
                error=str(e),
                processing_time=processing_time,
                exc_info=True
            )
            yield self.format_sse_message('compression_error', {
                'error': str(e),
                'compression_type': compression_type
            })

    async def _compress_tool_results(self, tool_results: List[Dict[str, Any]]) -> AsyncGenerator[Dict[str, Any], None]:
        """Compress tool results"""
        if not tool_results:
            yield {'status': 'completed', 'message': 'No tool results to compress'}
            return

        total_original_length = 0
        total_compressed_length = 0

        compressed_results = []

        for i, result in enumerate(tool_results):
            # Check if pre-compression is needed for large results
            if isinstance(result.get('content'), str):
                content_length = len(result['content'])
                precompress_threshold = self.compression_config[
                    'iteration_compression']['single_result_precompress_threshold']

                if content_length > precompress_threshold:
                    logger.debug(
                        "Pre-compressing large tool result",
                        result_index=i,
                        content_length=content_length,
                        threshold=precompress_threshold
                    )

                    # Use tool result compressor for large results
                    compression_result = await self.tool_result_compressor.compress_single_result(result)
                    compressed_results.append(compression_result)

                    total_original_length += len(result['content'])
                    total_compressed_length += len(
                        compression_result['content'])
                else:
                    compressed_results.append(result)
                    total_original_length += content_length
                    total_compressed_length += content_length
            else:
                compressed_results.append(result)

            # Report progress
            progress = (i + 1) / len(tool_results)
            yield {
                'status': 'progress',
                'progress': progress,
                'current_result': i + 1,
                'total_results': len(tool_results),
                'compression_ratio': total_compressed_length / total_original_length if total_original_length > 0 else 1.0
            }

        # Update stats
        if total_original_length > 0:
            self.compression_stats['compression_ratio'] = total_compressed_length / \
                total_original_length
        self.compression_stats['original_length'] = total_original_length
        self.compression_stats['compressed_length'] = total_compressed_length

        yield {
            'status': 'completed',
            'compressed_results': compressed_results,
            'original_length': total_original_length,
            'compressed_length': total_compressed_length,
            'compression_ratio': self.compression_stats['compression_ratio']
        }

    async def _compress_iteration_context(
        self,
        current_results: List[Dict[str, Any]],
        historical_context: List[Dict[str, Any]],
        iteration: int
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Compress iteration context between MCP tool calls"""
        # Use the iteration compressor
        compressed_context = self.iteration_compressor.compress_iteration_context(
            current_results,
            historical_context,
            iteration
        )

        # Calculate compression stats
        original_length = sum(len(str(r))
                              for r in historical_context + current_results)
        compressed_length = sum(len(str(r)) for r in compressed_context)

        self.compression_stats['original_length'] = original_length
        self.compression_stats['compressed_length'] = compressed_length
        self.compression_stats['compression_ratio'] = compressed_length / \
            original_length if original_length > 0 else 1.0

        yield {
            'status': 'completed',
            'compressed_context': compressed_context,
            'original_length': original_length,
            'compressed_length': compressed_length,
            'compression_ratio': self.compression_stats['compression_ratio'],
            'iteration': iteration
        }

    async def _compress_conversation_context(
        self,
        history: List[Dict[str, Any]],
        current_query: str
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Compress conversation context (placeholder for stage 2)"""
        # For now, just return the history as-is
        # This will be implemented in stage 2
        yield {
            'status': 'completed',
            'compressed_history': history,
            'message': 'Conversation context compression not yet implemented (Stage 2)'
        }

    def create_token_stats(self, *args: Any, **kwargs: Dict[str, Any]) -> BaseTokenStats:
        """Create token stats for compression operations"""
        from app.schemas.token_stats import CompressionTokenStats, TokenUsage

        # Estimate tokens based on content length
        original_tokens = self.token_calculator.estimate_tokens(
            "x" * self.compression_stats.get('original_length', 0)
        )
        compressed_tokens = self.token_calculator.estimate_tokens(
            "x" * self.compression_stats.get('compressed_length', 0)
        )

        token_usage = TokenUsage(
            prompt_tokens=original_tokens,
            completion_tokens=compressed_tokens,
            total_tokens=original_tokens + compressed_tokens
        )

        return CompressionTokenStats(
            agent_name="ContextCompressionAgent",
            model_name=self.model_name,
            think_mode=self.think_mode,
            model_limit=self.model_limit,
            token_usage=token_usage,
            compression_ratio=self.compression_stats.get(
                'compression_ratio', 1.0),
            processing_time=self.compression_stats.get('processing_time', 0.0),
            original_content_length=self.compression_stats.get(
                'original_length'),
            compressed_content_length=self.compression_stats.get(
                'compressed_length')
        )

    def get_compression_stats(self) -> Dict[str, Any]:
        """Get compression statistics"""
        return self.compression_stats.copy()


class ToolResultCompressor:
    """Tool result compressor that handles different content types"""

    def __init__(self, llm_config: LLMConfig, compression_config: Dict[str, Any]):
        self.llm_config = llm_config
        self.compression_config = compression_config
        self.generic_compressor = GenericCompressor()

    async def compress_single_result(self, tool_result: Dict[str, Any]) -> Dict[str, Any]:
        """Compress a single tool result based on its content type"""
        compressed_result = tool_result.copy()

        if not isinstance(tool_result.get('content'), str):
            return compressed_result

        content = tool_result['content']
        content_type = self._detect_result_type(tool_result)

        # Get max length for this content type
        max_length = self._get_max_length_for_type(content_type)

        # Compress using generic compressor
        compressor = GenericCompressor(max_length=max_length)
        compression_result = compressor.compress(content, content_type)

        compressed_result['content'] = compression_result.compressed_content
        compressed_result['compression_info'] = {
            'original_length': len(content),
            'compressed_length': len(compression_result.compressed_content),
            'compression_ratio': compression_result.compression_ratio,
            'content_type': content_type.value,  # Convert enum to string
            'key_info_extracted': compression_result.key_info_extracted
        }

        return compressed_result

    def _detect_result_type(self, tool_result: Dict[str, Any]) -> ContentType:
        """Detect the type of tool result"""
        tool_name = tool_result.get('tool_name', '').lower()
        content = tool_result.get('content', '')

        if 'tavily_extract' in tool_name:
            return ContentType.WEB_CONTENT
        elif 'tavily_search' in tool_name:
            return ContentType.SEARCH_RESULTS
        elif tool_result.get('content_type'):
            # Try to convert string to enum, fallback to GENERIC if invalid
            try:
                return ContentType(tool_result['content_type'])
            except ValueError:
                return ContentType.GENERIC
        else:
            # Auto-detect based on content
            return self.generic_compressor._detect_content_type(content)

    def _get_max_length_for_type(self, content_type: ContentType) -> int:
        """Get maximum length for content type"""
        config = self.compression_config['single_round']

        if content_type == ContentType.WEB_CONTENT:
            return config['max_web_content_length']
        elif content_type == ContentType.SEARCH_RESULTS:
            # Search results have different logic
            return config['max_generic_length']
        else:
            return config['max_generic_length']
