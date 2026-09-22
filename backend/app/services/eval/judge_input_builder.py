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
from app.services.eval.trace_media import resolve_image_refs
from app.utils.logger import logger

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

# 历史单轮文本上限：对话长时避免裁判 prompt 无界膨胀
HISTORY_TURN_MAX_CHARS = 1500


@dataclass
class JudgeInput:
    """线上裁判单条入参。"""

    query: str
    answer: str
    reference_xml: str = ""
    dialogue_history: str = ""
    source_flags: dict[str, Any] = field(default_factory=dict)
    images: list[str] = field(default_factory=list)


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


def extract_message_images(msg: dict[str, Any]) -> list[str]:
    """从消息 content 多模态块中抽取图片引用（data URI 或 langfuseMedia 标记）。"""
    content = msg.get("content")
    if not isinstance(content, list):
        return []
    refs: list[str] = []
    for item in content:
        if not isinstance(item, dict):
            continue
        item_type = str(item.get("type") or "")
        payload: Any = None
        if item_type in ("image_url", "input_image", "image"):
            payload = item.get("image_url") or item.get("image")
        elif "image_url" in item or "image" in item:
            payload = item.get("image_url") or item.get("image")
        if isinstance(payload, dict):
            payload = payload.get("url")
        if isinstance(payload, str) and payload.strip():
            refs.append(payload.strip())
    return refs


def normalize_generation_input(raw_input: Any) -> dict[str, Any]:
    """规范化 GENERATION input：保留 messages 等，去掉 tools schema。"""
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


def extract_generation_answer(raw_output: Any) -> str:
    """从 GENERATION output 抽出最终文本回答。"""
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


# 兼容旧私有名（测试 / 内部调用）
_normalize_generation_input = normalize_generation_input
_extract_generation_answer = extract_generation_answer


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


def format_dialogue_history(turns: list[tuple[str, str]]) -> str:
    """把历史轮 (role, text) 列表拼成 <dialogue_history> XML（仅供裁判理解上下文）。"""
    if not turns:
        return ""
    lines = ["<dialogue_history>"]
    for i, (role, text) in enumerate(turns, 1):
        lines.append(f'<hist_turn index="{i}" role="{role}">{text}</hist_turn>')
    lines.append("</dialogue_history>")
    return "\n".join(lines)


def build_reference_xml(
    *,
    attachment_context: str = "",
    tool_contents: list[str] | None = None,
) -> str:
    """拼参考资料 XML：attachment_context + tool 返回（不做截断）。"""
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
    for i, content in enumerate(parts, 1):
        body_parts.append(f"<来源_{i}>\n{content}\n</来源_{i}>")
    body_parts.append("</参考资料>")
    return "\n".join(body_parts)


def parse_generation_messages(
    messages: list[Any],
) -> tuple[str, list[str], str, list[str], list[str], str]:
    """从 GENERATION messages 解析 query / memories / attachment / tool contents / images / 历史。

    以「胜出的 user 消息」（即提供 query 的那条，通常是本轮）为界：
    - images 取胜出消息上的图片引用；若没有任何 user 消息胜出（如图片单独成块、无文本），
      回退到最后一条带图 user 消息；
    - tool_contents 只收胜出消息【之后】的 tool 返回（本轮工具），历史轮工具结果不混入；
    - dialogue_history 汇总胜出消息【之前】的 user/assistant 文本，仅供裁判理解指代，
      不作为事实依据。
    """
    query = ""
    memories: list[str] = []
    attachment = ""
    tool_contents: list[str] = []
    images: list[str] = []
    images_from_winner = False
    last_user_images: list[str] = []
    winner_idx = -1
    history_candidates: list[tuple[int, str, str]] = []
    tool_candidates: list[tuple[int, str]] = []

    for idx, msg in enumerate(messages):
        if not isinstance(msg, dict):
            continue
        role = str(msg.get("role") or "")
        msg_images = extract_message_images(msg) if role == "user" else []
        if msg_images:
            last_user_images = msg_images
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
                images = msg_images
                images_from_winner = True
                winner_idx = idx
            elif "<query>" not in content.lower() and not query:
                # 非 XML 的纯文本 user：仅在尚未有 query 时作为弱回退
                query = content.strip()
                images = msg_images
                images_from_winner = True
                winner_idx = idx
            # 历史轮 user：优先取 <query> 内文（回放文本是整段 XML，直接拼太吵）
            history_text = parsed_query or content.strip()
            history_candidates.append((idx, "user", _format_history_turn(history_text, msg_images)))
        elif role == "assistant":
            history_candidates.append(
                (idx, "assistant", _format_history_turn(content.strip(), []))
            )
        elif role == "tool":
            tool_candidates.append((idx, content.strip()))

    if not images_from_winner:
        images = last_user_images

    if winner_idx >= 0:
        # 以最终胜出消息（本轮）为界：之后的工具返回属于本轮，之前的属于历史轮
        tool_contents = [text for idx, text in tool_candidates if idx > winner_idx]
        history_turns = [
            (role, text) for idx, role, text in history_candidates if idx < winner_idx
        ]
    else:
        # 无胜出消息时保持旧行为：工具返回全收、无历史
        tool_contents = [text for _, text in tool_candidates]
        history_turns = []
    dialogue_history = format_dialogue_history(history_turns)

    return query, memories, attachment, tool_contents, images, dialogue_history


def _format_history_turn(text: str, images: list[str]) -> str:
    """历史单轮文本：截断超长内容，并标注未随评估提供的图片。"""
    if len(text) > HISTORY_TURN_MAX_CHARS:
        text = text[: HISTORY_TURN_MAX_CHARS - 8] + "…[截断]"
    if images:
        note = f"[该消息附带 {len(images)} 张图片，未随评估提供]"
        text = f"{text}\n{note}" if text else note
    return text


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
        "metadata": getattr(obs, "metadata", None),
        "start_time": getattr(obs, "start_time", None),
        "startTime": getattr(obs, "startTime", None),
    }


def _obs_type(obs: dict[str, Any]) -> str:
    return str(obs.get("type") or "").upper()


def _obs_start_time(obs: dict[str, Any]) -> str:
    return str(obs.get("start_time") or obs.get("startTime") or "")


def fetch_last_generation(
    langfuse_client: Any | None,
    trace_id: str,
    *,
    fields: str = "core,io,metadata",
) -> dict[str, Any] | None:
    """拉取 trace 下最后一条 type=GENERATION 的 observation（含 IO）。"""
    if not trace_id or langfuse_client is None:
        return None
    api = getattr(langfuse_client, "api", None)
    observations_api = getattr(api, "observations", None) if api is not None else None
    if observations_api is None or not hasattr(observations_api, "get_many"):
        return None
    try:
        response = observations_api.get_many(
            trace_id=trace_id,
            limit=50,
            fields=fields,
        )
    except Exception as exc:
        logger.warning(
            "Failed to fetch generation observations",
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
            "image_count": 0,
            "image_failed": 0,
        }

        generation = self._fetch_last_generation(str(trace.get("id") or ""))
        query = chat_query
        answer = chat_answer
        reference_xml = ""
        memories: list[str] = []
        attachment = ""
        tool_contents: list[str] = []
        image_refs: list[str] = []
        dialogue_history = ""

        if generation is not None:
            source_flags["last_generation"] = True
            gen_input = normalize_generation_input(generation.get("input"))
            messages = gen_input.get("messages") or []
            if not isinstance(messages, list):
                messages = []
            query, memories, attachment, tool_contents, image_refs, dialogue_history = (
                parse_generation_messages(messages)
            )
            gen_answer = extract_generation_answer(generation.get("output"))
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

        images = resolve_image_refs(image_refs)
        source_flags["image_count"] = len(images)
        source_flags["image_failed"] = max(0, len(image_refs) - len(images))
        source_flags["history_turns"] = dialogue_history.count("<hist_turn")

        return JudgeInput(
            query=judge_query,
            answer=answer or chat_answer,
            reference_xml=reference_xml,
            dialogue_history=dialogue_history,
            source_flags=source_flags,
            images=images,
        )

    def _fetch_last_generation(self, trace_id: str) -> dict[str, Any] | None:
        return fetch_last_generation(self.langfuse, trace_id)

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
                        .order_by(desc(MessageDb.created_at))  # type: ignore[arg-type]
                    ).first()

                if assistant and isinstance(assistant.content_blocks, list):
                    # JSON 列运行时可能非 dict；放宽元素类型以保留守卫
                    blocks: list[Any] = assistant.content_blocks
                    for block in blocks:
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
