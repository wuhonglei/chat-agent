"""共享的流式最终应答 SSE 生成（从原 ResponseGenerationAgent 抽取）。"""

from collections.abc import AsyncIterator, Callable
from typing import Any

from app.utils.logger import logger
from app.utils.time import get_current_time, get_time_duration


def finish_streaming_type(
    format_sse_message: Callable[[str, dict[str, Any] | None], str],
    msg_type: str,
    fallback_content: str = "",
) -> str:
    """结束某个类型的流式输出"""
    return format_sse_message(
        msg_type,
        {
            "status": "done",
            "content": fallback_content,
        },
    )


async def stream_final_response_sse(
    *,
    call_llm_api: Callable[..., Any],
    model: str,
    messages: list[dict[str, Any]],
    extra_body: dict[str, Any],
    format_sse_message: Callable[[str, dict[str, Any] | None], str],
) -> AsyncIterator[str]:
    """消费 LLM 流式 chunk，产出 reasoning / content 的 SSE 字符串。"""
    start_time = get_current_time()
    response = await call_llm_api(
        model=model,
        messages=messages,
        stream=True,
        extra_body=extra_body,
    )

    current_phase = None  # None, 'reasoning', 'content'
    phase_start_time = None

    async for chunk in response:
        if not chunk.choices or not getattr(chunk.choices[0], "delta", None):
            continue

        delta = chunk.choices[0].delta
        reasoning_content = getattr(delta, "reasoning_content", None)
        content = getattr(delta, "content", None)

        if reasoning_content:
            if current_phase != "reasoning":
                current_phase = "reasoning"
                phase_start_time = get_current_time()
                yield format_sse_message(
                    "reasoning",
                    {
                        "status": "start",
                        "content": reasoning_content,
                    },
                )
            else:
                yield format_sse_message(
                    "reasoning",
                    {
                        "status": "continue",
                        "content": reasoning_content,
                    },
                )

        if content:
            if current_phase == "reasoning":
                assert phase_start_time is not None
                yield finish_streaming_type(format_sse_message, "reasoning")
                current_phase = "content"
                phase_start_time = get_current_time()
                yield format_sse_message(
                    "content",
                    {
                        "status": "start",
                        "content": content,
                    },
                )
            elif current_phase != "content":
                current_phase = "content"
                phase_start_time = get_current_time()
                yield format_sse_message(
                    "content",
                    {
                        "status": "start",
                        "content": content,
                    },
                )
            else:
                yield format_sse_message(
                    "content",
                    {
                        "status": "continue",
                        "content": content,
                    },
                )

    if current_phase == "reasoning":
        assert phase_start_time is not None
        yield finish_streaming_type(format_sse_message, "reasoning")
        yield finish_streaming_type(
            format_sse_message,
            "content",
            "[模型已完成深入推理，详见思考过程]",
        )
    elif current_phase == "content":
        assert phase_start_time is not None
        yield finish_streaming_type(format_sse_message, "content")

    logger.info(
        "Stream final response completed",
        duration=get_time_duration(start_time),
    )
