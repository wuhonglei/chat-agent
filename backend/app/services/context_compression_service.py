"""Context Compression Service for compressing tool results and conversation context"""

from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

from app.core.config import settings
from app.utils.compression import ContextMonitor
from app.utils.logger import logger
from app.utils.time import get_current_time, get_time_duration


@dataclass
class CompressionResult:
    """Compression result with statistics"""
    compressed_messages: List[Any]
    original_length: int
    compressed_length: int
    compression_ratio: float
    duration: float
    was_compressed: bool


class ContextCompressionService:
    """Service for handling context compression operations"""

    def __init__(self, model_name: str):
        """
        Initialize context compression service

        Args:
            model_name: LLM model name for token calculations
        """
        self.model_name = model_name
        self.context_monitor = ContextMonitor(model_name)
        # Set compression threshold from config
        self.context_monitor.compression_threshold = settings.compression.iteration_compression.compression_trigger_threshold

    async def compress_tool_messages(
        self,
        messages: List[Any],
        force_compress: bool = False
    ) -> CompressionResult:
        """
        Compress tool messages if needed

        Args:
            messages: List of tool call messages to potentially compress
            force_compress: Whether to force compression regardless of threshold

        Returns:
            CompressionResult: Compression result with statistics
        """
        if not messages:
            return CompressionResult(
                compressed_messages=[],
                original_length=0,
                compressed_length=0,
                compression_ratio=1.0,
                duration=0.0,
                was_compressed=False
            )

        start_time = get_current_time()

        logger.debug("Starting context compression for tool messages",
                     message_count=len(messages))

        # Calculate original length
        original_length = sum(len(str(msg)) for msg in messages)

        # Decide whether to compress
        should_compress = force_compress or (
            original_length > self.context_monitor.compression_threshold)

        if should_compress:
            # Perform compression
            compressed_messages = self.context_monitor.check_and_compress(
                messages)
            compressed_length = sum(len(str(msg))
                                    for msg in compressed_messages)
            compression_ratio = compressed_length / \
                original_length if original_length > 0 else 1.0
            was_compressed = True

            logger.debug(
                "Context compression completed",
                original_length=original_length,
                compressed_length=compressed_length,
                compression_ratio=compression_ratio,
                threshold=self.context_monitor.compression_threshold
            )
        else:
            # No compression needed
            compressed_messages = messages
            compressed_length = original_length
            compression_ratio = 1.0
            was_compressed = False

            logger.debug(
                "Context compression skipped - below threshold",
                original_length=original_length,
                threshold=self.context_monitor.compression_threshold
            )

        duration = get_time_duration(start_time)

        return CompressionResult(
            compressed_messages=compressed_messages,
            original_length=original_length,
            compressed_length=compressed_length,
            compression_ratio=compression_ratio,
            duration=duration,
            was_compressed=was_compressed
        )

    def update_compression_threshold(self, new_threshold: int) -> None:
        """
        Update the compression threshold

        Args:
            new_threshold: New compression threshold value
        """
        logger.info(
            "Updating compression threshold",
            old_threshold=self.context_monitor.compression_threshold,
            new_threshold=new_threshold
        )
        self.context_monitor.compression_threshold = new_threshold

    def get_compression_stats(self) -> Dict[str, Any]:
        """
        Get current compression configuration and statistics

        Returns:
            Dict containing compression settings
        """
        return {
            'compression_threshold': self.context_monitor.compression_threshold,
            'model_name': self.model_name,
            'compression_enabled': True
        }
