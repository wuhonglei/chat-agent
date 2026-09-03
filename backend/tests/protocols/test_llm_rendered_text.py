"""llm_rendered_text 历史回放与 token 计数单测。"""

from __future__ import annotations

from app.protocols.chat_messages import (
    format_chat_message_for_llm,
    resolve_user_llm_rendered_text,
)
from app.schemas.chat import ChatMessage, ImageBlock, TextBlock
from app.utils.history_truncate import count_chat_message_tokens
from app.utils.token import TokenCalculator


def _user_msg(
    *,
    text: str = "裸 query",
    llm_rendered_text: str | None = None,
    with_image: bool = False,
) -> ChatMessage:
    blocks: list[TextBlock | ImageBlock] = [TextBlock(id="t1", text=text)]
    if with_image:
        blocks.append(
            ImageBlock(
                id="img1",
                url="data:image/png;base64,iVBORw0KGgo=",
                size=12,
                mime="image/png",
                name="a.png",
            )
        )
    metadata: dict[str, object] = {}
    if llm_rendered_text is not None:
        metadata["llm_rendered_text"] = llm_rendered_text
    return ChatMessage(
        id="u1",
        conversation_id="c1",
        role="user",
        content_blocks=blocks,
        status="done",
        message_metadata=metadata,
    )


def test_resolve_user_llm_rendered_text_returns_snapshot() -> None:
    msg = _user_msg(llm_rendered_text="  <user_message>wrapped</user_message>  ")
    assert resolve_user_llm_rendered_text(msg) == "<user_message>wrapped</user_message>"


def test_resolve_user_llm_rendered_text_missing_returns_none() -> None:
    assert resolve_user_llm_rendered_text(_user_msg()) is None
    assert resolve_user_llm_rendered_text(_user_msg(llm_rendered_text="   ")) is None


def test_format_prefers_llm_rendered_text_snapshot() -> None:
    rendered = (
        "<user_message>\n  <query>裸 query</query>\n</user_message>\n\n"
        "<tool_call_context>\n  <current_datetime>2026-09-03 12:00:00</current_datetime>\n"
        "</tool_call_context>"
    )
    payload = format_chat_message_for_llm(
        _user_msg(llm_rendered_text=rendered)
    )
    assert payload["role"] == "user"
    assert payload["content"] == rendered
    assert "裸 query" in payload["content"]
    assert "<tool_call_context>" in payload["content"]


def test_format_falls_back_to_raw_content_blocks() -> None:
    payload = format_chat_message_for_llm(_user_msg(text="仅裸文本"))
    assert payload["content"] == "仅裸文本"


def test_format_with_snapshot_and_image_skips_duplicate_text_blocks() -> None:
    rendered = (
        "<user_message>\n  <query>[用户发送了图片]</query>\n</user_message>\n\n"
        "<tool_call_context>\n  <current_datetime>2026-09-03 12:00:00</current_datetime>\n"
        "</tool_call_context>"
    )
    payload = format_chat_message_for_llm(
        _user_msg(text="", llm_rendered_text=rendered, with_image=True)
    )
    assert isinstance(payload["content"], list)
    text_parts = [
        p["text"] for p in payload["content"] if p.get("type") == "text"
    ]
    image_parts = [p for p in payload["content"] if p.get("type") == "image_url"]
    assert len(text_parts) == 1
    assert text_parts[0] == rendered
    assert len(image_parts) == 1


def test_count_chat_message_tokens_uses_rendered_snapshot() -> None:
    calc = TokenCalculator(model="gpt-4o", context_limit=128_000)
    bare = _user_msg(text="短问题")
    big_rag = "RAG 段落 " * 500
    rendered = (
        f"<user_message>\n  <query>短问题</query>\n"
        f"  <attachment_context>\n    <attachment index=\"1\">\n"
        f"      <name>doc.md</name>\n      <content>{big_rag}</content>\n"
        f"    </attachment>\n  </attachment_context>\n</user_message>\n\n"
        f"<tool_call_context>\n  <current_datetime>2026-09-03 12:00:00</current_datetime>\n"
        f"</tool_call_context>"
    )
    with_snapshot = _user_msg(text="短问题", llm_rendered_text=rendered)

    bare_tokens = count_chat_message_tokens(bare, calc)
    snapshot_tokens = count_chat_message_tokens(with_snapshot, calc)
    assert snapshot_tokens > bare_tokens
    assert snapshot_tokens > calc.count_tokens("短问题")
