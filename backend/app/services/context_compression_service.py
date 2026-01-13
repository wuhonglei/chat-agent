"""Context Compression Service for compressing tool results and conversation context"""

from dataclasses import dataclass
from typing import Any

from app.utils.compression import ContextMonitor
from app.utils.logger import logger
from app.utils.time import get_current_time, get_time_duration
from app.utils.token import TokenCalculator


@dataclass
class CompressionResult:
    """Compression result with statistics"""

    compressed_messages: list[Any]
    original_length: int
    compressed_length: int
    compression_ratio: float
    duration: float
    was_compressed: bool


class ContextCompressionService:
    """Service for handling context compression operations"""

    def __init__(self, token_calculator: TokenCalculator, compression_threshold: int):
        """
        Initialize context compression service

        Args:
            token_calculator: Token calculator for token calculations
        """
        self.token_calculator = token_calculator
        self.context_monitor = ContextMonitor(token_calculator, compression_threshold)

    async def compress_tool_messages(
        self, messages: list[Any], force_compress: bool = False
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
                was_compressed=False,
            )

        start_time = get_current_time()

        logger.debug(
            "Starting context compression for tool messages",
            message_count=len(messages),
        )

        # Calculate original length
        original_length = self.token_calculator.count_messages_tokens(messages)

        # Decide whether to compress
        should_compress = force_compress or (
            original_length > self.context_monitor.compression_threshold
        )

        if should_compress:
            # Perform compression
            compressed_messages = self.context_monitor.check_and_compress(messages)
            compressed_length = self.token_calculator.count_messages_tokens(
                compressed_messages
            )
            compression_ratio = (
                compressed_length / original_length if original_length > 0 else 1.0
            )
            was_compressed = True

            logger.debug(
                "Context compression completed",
                original_length=original_length,
                compressed_length=compressed_length,
                compression_ratio=compression_ratio,
                threshold=self.context_monitor.compression_threshold,
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
                threshold=self.context_monitor.compression_threshold,
            )

        duration = get_time_duration(start_time)

        return CompressionResult(
            compressed_messages=compressed_messages,
            original_length=original_length,
            compressed_length=compressed_length,
            compression_ratio=compression_ratio,
            duration=duration,
            was_compressed=was_compressed,
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
            new_threshold=new_threshold,
        )
        self.context_monitor.compression_threshold = new_threshold
