"""从 Langfuse last GENERATION（及 DB 兜底）组装线上裁判输入。"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import desc
from sqlmodel import Session, select

from app.core.db import engine
from app.models.message_db import MessageDb
from app.utils.logger import logger

REFERENCE_MAX_CHARS = 12_000
ANSWER_MAX_CHARS = 4_000
QUERY_TAG_RE = re.compile(r"<query>(.*?)</query>", re.DOTALL | re.IGNORECASE)
MEMORIES_BLOCK_RE = re.compile(
    r"<user_memories>(.*?)</user_memories>", re.DOTALL | re.IGNORECASE
)
MEMORY_ITEM_RE = re.compile(
    r"<memory_item>(.*?)</memory_item>", re.DOTALL | re.IGNORECASE
)
MEMORY_TEXT_RE = re.compile(r"<memory>(.*?)</memory>", re.DOTALL | re.IGNORECASE)
ATTACHMENT_CONTEXT_RE = re.compile(
    r"<attachment_context>(.*?)</attachment_context>", re.DOTALL | re.IGNORECASE
)


@dataclass
class JudgeInput:
    """线上裁判单条入参。"""

    query: str
    answer: str
    reference_xml: str = ""
    source_flags: dict[str, Any] = field(default_factory=dict)


def _as_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if value is None:
        return ""
    return str(value)


def _metadata(trace: dict[str, Any]) -> dict[str, Any]:
    meta = trace.get("metadata") or {}
    return meta if isinstance(meta, dict) else {}


def _message_content(msg: dict[str, Any]) -> str:
    content = msg.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text") or item.get("content")
                if text:
                    parts.append(str(text))
            elif isinstance(item, str):
                parts.append(item)
        return "\n".join(parts)
    if content is None:
        return ""
    return str(content)


def _normalize_generation_input(raw_input: Any) -> dict[str, Any]:
    data = raw_input
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError:
            return {"messages": [{"role": "user", "content": data}]}
    if not isinstance(data, dict):
        return {}
    # 去掉 tools schema，避免噪声与超长
    return {k: v for k, v in data.items() if k != "tools"}


def _extract_generation_answer(raw_output: Any) -> str:
    if raw_output is None:
        return ""
    if isinstance(raw_output, str):
        return raw_output.strip()
    if isinstance(raw_output, dict):
        content = raw_output.get("content")
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    text = item.get("text")
                    if text:
                        parts.append(str(text))
                elif isinstance(item, str):
                    parts.append(item)
            if parts:
                return "\n".join(parts).strip()
        # OpenAI-compatible: choices[0].message.content
        choices = raw_output.get("choices")
        if isinstance(choices, list) and choices:
            message = (
                choices[0].get("message") if isinstance(choices[0], dict) else None
            )
            if isinstance(message, dict):
                return _as_text(message.get("content")).strip()
        return _as_text(content or raw_output.get("text") or "").strip()
    return _as_text(raw_output).strip()


def _xml_inner(pattern: re.Pattern[str], text: str) -> str:
    match = pattern.search(text)
    return match.group(1).strip() if match else ""


def parse_user_xml(user_content: str) -> tuple[str, list[str], str]:
    """从 user XML 抽出 query、memory 文本列表、attachment_context 内文。"""
    query = _xml_inner(QUERY_TAG_RE, user_content)
    memories: list[str] = []
    mem_block = _xml_inner(MEMORIES_BLOCK_RE, user_content)
    if mem_block:
        items = MEMORY_ITEM_RE.findall(mem_block)
        if items:
            for item in items:
                memory = _xml_inner(MEMORY_TEXT_RE, item)
                if memory:
                    memories.append(memory)
        else:
            # 容错：无 memory_item 时按行取
            for line in mem_block.splitlines():
                line = line.strip(" -*\t")
                if line:
                    memories.append(line)
    attachment = _xml_inner(ATTACHMENT_CONTEXT_RE, user_content)
    return query, memories, attachment


def build_judge_query(query: str, memories: list[str]) -> str:
    """构造裁判用 query（可附 user_memories）。"""
    query = query.strip()
    if not memories:
        return query
    mem_lines = "\n".join(f"- {m}" for m in memories)
    suffix = f"<user_memories>\n{mem_lines}\n</user_memories>"
    if not query:
        return suffix
    return f"{query}\n\n{suffix}"


def build_reference_xml(
    *,
    attachment_context: str = "",
    tool_contents: list[str] | None = None,
    max_chars: int = REFERENCE_MAX_CHARS,
) -> str:
    """拼参考资料 XML：attachment_context + tool 返回。"""
    parts: list[str] = []
    if attachment_context.strip():
        parts.append(
            "<attachment_context>\n"
            + attachment_context.strip()
            + "\n</attachment_context>"
        )
    for content in tool_contents or []:
        text = content.strip()
        if text:
            parts.append(text)

    if not parts:
        return ""

    body_parts = ["<参考资料>"]
    used = len(body_parts[0]) + len("</参考资料>")
    for i, content in enumerate(parts, 1):
        chunk = f"<来源_{i}>\n{content}\n</来源_{i}>"
        if used + len(chunk) + 1 > max_chars:
            remain = max_chars - used - 32
            if remain > 200:
                truncated = content[:remain] + "\n…(truncated)"
                body_parts.append(f"<来源_{i}>\n{truncated}\n</来源_{i}>")
            break
        body_parts.append(chunk)
        used += len(chunk) + 1
    body_parts.append("</参考资料>")
    return "\n".join(body_parts)


def parse_generation_messages(
    messages: list[Any],
) -> tuple[str, list[str], str, list[str]]:
    """从 GENERATION messages 解析 query / memories / attachment / tool contents。"""
    query = ""
    memories: list[str] = []
    attachment = ""
    tool_contents: list[str] = []

    for msg in messages:
        if not isinstance(msg, dict):
            continue
        role = str(msg.get("role") or "")
        content = _message_content(msg)
        if not content.strip():
            continue

        if role == "user":
            parsed_query, parsed_memories, parsed_attachment = parse_user_xml(content)
            if parsed_query or parsed_memories or parsed_attachment:
                # 取最后一条带结构化 user XML 的消息（本 turn）
                if parsed_query:
                    query = parsed_query
                if parsed_memories:
                    memories = parsed_memories
                if parsed_attachment:
                    attachment = parsed_attachment
            elif "<query>" not in content.lower() and not query:
                # 非 XML 的纯文本 user：仅在尚未有 query 时作为弱回退
                query = content.strip()
        elif role == "tool":
            tool_contents.append(content.strip())

    return query, memories, attachment, tool_contents


def _obs_to_dict(obs: Any) -> dict[str, Any]:
    if isinstance(obs, dict):
        return obs
    if hasattr(obs, "model_dump"):
        return dict(obs.model_dump())
    if hasattr(obs, "dict"):
        return dict(obs.dict())
    return {
        "id": getattr(obs, "id", None),
        "type": getattr(obs, "type", None),
        "input": getattr(obs, "input", None),
        "output": getattr(obs, "output", None),
        "start_time": getattr(obs, "start_time", None),
        "startTime": getattr(obs, "startTime", None),
    }


def _obs_type(obs: dict[str, Any]) -> str:
    return str(obs.get("type") or "").upper()


def _obs_start_time(obs: dict[str, Any]) -> str:
    return str(obs.get("start_time") or obs.get("startTime") or "")


class JudgeInputBuilder:
    """按采样 trace 组装裁判输入。"""

    def __init__(self, langfuse_client: Any | None = None) -> None:
        self.langfuse = langfuse_client

    def build_from_trace(self, trace: dict[str, Any]) -> JudgeInput:
        """同步组装（Langfuse SDK 调用为同步）。"""
        chat_query = _as_text(trace.get("input", "")).strip()
        chat_answer = _as_text(trace.get("output", "")).strip()
        source_flags: dict[str, Any] = {
            "last_generation": False,
            "db_fallback": False,
            "chat_turn_only": False,
            "has_memories": False,
            "has_attachment_context": False,
            "tool_count": 0,
        }

        generation = self._fetch_last_generation(str(trace.get("id") or ""))
        query = chat_query
        answer = chat_answer
        reference_xml = ""
        memories: list[str] = []
        attachment = ""
        tool_contents: list[str] = []

        if generation is not None:
            source_flags["last_generation"] = True
            gen_input = _normalize_generation_input(generation.get("input"))
            messages = gen_input.get("messages") or []
            if not isinstance(messages, list):
                messages = []
            query, memories, attachment, tool_contents = parse_generation_messages(
                messages
            )
            gen_answer = _extract_generation_answer(generation.get("output"))
            if gen_answer:
                answer = gen_answer
            if not query:
                query = chat_query
            if not answer:
                answer = chat_answer
            reference_xml = build_reference_xml(
                attachment_context=attachment,
                tool_contents=tool_contents,
            )
            source_flags["has_memories"] = bool(memories)
            source_flags["has_attachment_context"] = bool(attachment.strip())
            source_flags["tool_count"] = len(tool_contents)
        else:
            source_flags["chat_turn_only"] = True

        if not reference_xml:
            db_ref, db_memories = self._db_fallback(trace)
            if db_ref or db_memories:
                source_flags["db_fallback"] = True
                source_flags["chat_turn_only"] = False
                if db_memories and not memories:
                    memories = db_memories
                    source_flags["has_memories"] = True
                if db_ref:
                    reference_xml = db_ref
                    source_flags["tool_count"] = max(
                        source_flags["tool_count"], db_ref.count("<来源_")
                    )

        judge_query = build_judge_query(query or chat_query, memories)
        if not judge_query and not answer:
            source_flags["chat_turn_only"] = True

        return JudgeInput(
            query=judge_query,
            answer=(answer or chat_answer)[:ANSWER_MAX_CHARS],
            reference_xml=reference_xml,
            source_flags=source_flags,
        )

    def _fetch_last_generation(self, trace_id: str) -> dict[str, Any] | None:
        if not trace_id or self.langfuse is None:
            return None
        api = getattr(self.langfuse, "api", None)
        observations_api = (
            getattr(api, "observations", None) if api is not None else None
        )
        if observations_api is None or not hasattr(observations_api, "get_many"):
            return None
        try:
            response = observations_api.get_many(
                trace_id=trace_id,
                limit=50,
                fields="core,io",
            )
        except Exception as exc:
            logger.warning(
                "Failed to fetch generation observations for judge input",
                trace_id=trace_id,
                error=exc,
                error_type=type(exc).__name__,
            )
            return None

        data = getattr(response, "data", None) or []
        generations = [
            _obs_to_dict(item)
            for item in data
            if _obs_type(_obs_to_dict(item)) == "GENERATION"
        ]
        if not generations:
            return None
        # API 通常按 start_time 降序；再保险按时间排序取最后一条
        generations.sort(key=_obs_start_time, reverse=True)
        return generations[0]

    def _db_fallback(self, trace: dict[str, Any]) -> tuple[str, list[str]]:
        """reference 为空时从 messages 抽 tool_result / user_memories。"""
        meta = _metadata(trace)
        assistant_id = str(
            meta.get("assistant_message_id") or meta.get("message_id") or ""
        ).strip()
        conversation_id = str(meta.get("conversation_id") or "").strip()
        user_message_id = str(meta.get("user_message_id") or "").strip()

        if not assistant_id and not conversation_id:
            return "", []

        try:
            with Session(engine) as db:
                tool_contents: list[str] = []
                memories: list[str] = []

                assistant: MessageDb | None = None
                if assistant_id:
                    assistant = db.get(MessageDb, assistant_id)
                if assistant is None and conversation_id:
                    # 兜底：取会话内最近一条 assistant
                    assistant = db.exec(
                        select(MessageDb)
                        .where(MessageDb.conversation_id == conversation_id)
                        .where(MessageDb.role == "assistant")
                        .order_by(desc(MessageDb.created_at))
                    ).first()

                if assistant and isinstance(assistant.content_blocks, list):
                    for block in assistant.content_blocks:
                        if not isinstance(block, dict):
                            continue
                        if block.get("type") != "tool_result":
                            continue
                        content = block.get("content")
                        if content and str(content).strip():
                            tool_contents.append(str(content).strip())

                user_msg: MessageDb | None = None
                if user_message_id:
                    user_msg = db.get(MessageDb, user_message_id)
                elif assistant and assistant.reply_to:
                    user_msg = db.get(MessageDb, assistant.reply_to)

                if user_msg and isinstance(user_msg.message_metadata, dict):
                    raw_memories = user_msg.message_metadata.get("user_memories") or []
                    if isinstance(raw_memories, list):
                        for item in raw_memories:
                            if isinstance(item, dict):
                                memory = item.get("memory")
                                if memory:
                                    memories.append(str(memory).strip())
                            elif isinstance(item, str) and item.strip():
                                memories.append(item.strip())

                reference_xml = build_reference_xml(tool_contents=tool_contents)
                return reference_xml, memories
        except Exception as exc:
            logger.warning(
                "DB fallback for judge input failed",
                conversation_id=conversation_id,
                assistant_message_id=assistant_id,
                error=exc,
                error_type=type(exc).__name__,
            )
            return "", []
