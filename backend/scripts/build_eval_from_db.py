"""从数据库 messages 表直接构造评估集（绕过 Langfuse API）。

用法:
    uv run python scripts/build_eval_from_db.py
"""

import json
import subprocess
from pathlib import Path

from sqlalchemy import text

from app.core.db import get_db

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "data" / "eval_set" / "v1.0"
TARGET_USER = "c7d40833-6b26-4696-828f-a94b9de5b47d"
TARGET_SIZE = 120  # 目标采样量
API_BASE = "https://chat.wuhonglei.cn"

# 附件类型集合（非 text / tool_result 的 block 类型）
ATTACHMENT_TYPES = {"pdf", "image", "xlsx", "docx", "pptx", "markdown", "text_file"}


# 过滤关键词
IMG_KW = [
    "图中",
    "图片",
    "截图",
    "图一",
    "图二",
    "图三",
    "这张",
    "图像",
    "照片",
    "看图",
    "图片里",
]
FILTER_KW = [
    "湖北 2026 一本线",
    "今天有什么热点新闻",
    "你好呀",
    "为什么让 ai 执行 bash 命令",
    "deepseek agent 是什么",
    "当前 Hermes Agent 在进行 skill 执行前",
    "使用该软件时提示：协议模式未配置",
    "如何使用 pm2 查看应用日志",
    "我最近在用 hermes agent 吗",
]


def fetch_derived_markdown(url: str) -> str | None:
    """通过 API 获取附件派生的 markdown 内容。"""
    full_url = f"{API_BASE}{url}"
    try:
        r = subprocess.run(
            ["curl", "-s", "--connect-timeout", "10", "--max-time", "30", full_url],
            capture_output=True,
            text=True,
            timeout=35,
        )
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout
    except Exception:
        pass
    return None


def extract_attachment_context(blocks: list[dict]) -> str | None:
    """从用户消息的 content_blocks 中提取附件 context。"""
    parts = []
    for block in blocks:
        btype = block.get("type", "")
        if btype in ("text", "tool_result", "image"):
            continue
        name = block.get("name", "")
        size = block.get("size", 0)
        mime = block.get("mime", "")
        md = block.get("markdown")

        # 描述性元数据
        desc_lines = [
            f"文件名: {name}",
            f"类型: {btype} ({mime})",
            f"大小: {size} bytes",
        ]
        if md:
            md_name = md.get("name", "")
            md_size = md.get("size", 0)
            md_tokens = md.get("token_size")
            md_lines = md.get("lines_count")
            desc_lines.append(
                f"派生 Markdown: {md_name} ({md_size} bytes"
                + (f", {md_tokens} tokens" if md_tokens else "")
                + (f", {md_lines} lines" if md_lines else "")
                + ")"
            )
        parts.append("\n".join(desc_lines))

        # 尝试获取 markdown 完整内容
        if md and md.get("url"):
            content = fetch_derived_markdown(md["url"])
            if content:
                parts.append(content)

    if not parts:
        return None
    return "<attachment>\n" + "\n\n".join(parts) + "\n</attachment>"


def build_eval_from_db():
    session = next(get_db())

    # 1. 获取目标用户的所有 conversation
    result = session.execute(
        text("""
            SELECT c.id, c.created_at
            FROM conversations c
            WHERE c.user_id = :uid
            ORDER BY c.created_at DESC
        """),
        {"uid": TARGET_USER},
    )
    conversations = [(r[0], r[1]) for r in result]
    print(f"User conversations: {len(conversations)}")

    # 2. 对每个 conversation，提取第一条 user 消息 + assistant 回复 + tool_result
    eval_items = []
    for conv_id, conv_time in conversations:
        # 获取该 conversation 的所有消息
        result = session.execute(
            text("""
                SELECT role, content_blocks, created_at, status
                FROM messages
                WHERE conversation_id = :cid
                ORDER BY created_at ASC
            """),
            {"cid": conv_id},
        )
        messages = list(result)
        if not messages:
            continue

        # 提取首条 user query
        query = None
        first_user_idx = None
        for i, (role, blocks, created_at, status) in enumerate(messages):
            if role != "user" or not blocks:
                continue
            for block in blocks:
                if block.get("type") == "text":
                    query = block.get("text", "").strip()
                    break
            if query:
                first_user_idx = i
                break

        if not query or first_user_idx is None:
            continue

        # 提取首条 assistant answer（紧跟首条 user 之后的第一条 assistant）
        answer = None
        for role, blocks, created_at, status in messages[first_user_idx + 1 :]:
            if role != "assistant" or not blocks:
                continue
            # 取最后一个 text block（最终回答）
            for block in reversed(blocks):
                if block.get("type") == "text":
                    txt = block.get("text", "").strip()
                    if txt and len(txt) > 10:  # 过滤掉极短的中间轮
                        answer = txt
                        break
            if answer:
                break

        if not answer:
            continue

        # 提取首条 assistant 的 tool_result 作为 context
        context_parts = []
        for role, blocks, created_at, status in messages[first_user_idx + 1 :]:
            if role != "assistant" or not blocks:
                continue
            for block in blocks:
                if block.get("type") == "tool_result":
                    content = block.get("content", "")
                    if content:
                        context_parts.append(f"<tool>\n{content[:3000]}\n</tool>")
            break  # 只取首条 assistant 的 tool_result

        # 提取首条 user 的附件 context（pdf/xlsx/docx 等派生 markdown）
        first_user_blocks = messages[first_user_idx][1]
        if first_user_blocks:
            att_ctx = extract_attachment_context(first_user_blocks)
            if att_ctx:
                context_parts.append(att_ctx)

        # 应用过滤
        if any(kw in query for kw in IMG_KW):
            continue
        if any(kw in query for kw in FILTER_KW):
            continue
        if len(query) < 5:
            continue

        eval_items.append(
            {
                "trace_id": conv_id,  # 用 conversation_id 作为 trace_id
                "session_id": conv_id,
                "user_id": TARGET_USER,
                "timestamp": conv_time.isoformat() if conv_time else "",
                "query": query,
                "answer": answer,
                "context": "\n\n".join(context_parts) if context_parts else None,
                "model_id": "unknown",
                "agent_mode": 0,
                "latency_s": None,
                "cost_usd": None,
                "has_existing_scores": False,
                "langfuse_url": "",
                "annotation": {
                    "ground_truth_points": [],
                    "scene_tag": "",
                    "correctness_score": None,
                    "completeness_score": None,
                    "notes": "",
                },
            }
        )

    print(f"After extraction: {len(eval_items)}")

    # 3. query 去重
    seen = set()
    deduped = []
    for item in eval_items:
        if item["query"] not in seen:
            seen.add(item["query"])
            deduped.append(item)
    print(f"After dedup: {len(deduped)}")

    # 4. 优先采样有 context 的，按 55:45 比例（接近真实分布 55.4%）
    with_ctx = [x for x in deduped if x.get("context")]
    without_ctx = [x for x in deduped if not x.get("context")]
    ctx_take = min(len(with_ctx), round(TARGET_SIZE * 0.55))  # 66
    remain = TARGET_SIZE - ctx_take
    final = with_ctx[:ctx_take] + without_ctx[:remain]
    print(f"Final: {len(final)}")
    print(f"  Has context: {len([x for x in final if x.get('context')])}")
    print(f"  No context: {len([x for x in final if not x.get('context')])}")

    # 5. 写入文件
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    eval_path = OUTPUT_DIR / "eval_samples.json"
    eval_path.write_text(json.dumps(final, ensure_ascii=False, indent=2))
    print(f"Written: {eval_path}")

    # 同时写 annotated 版本（清空 annotation）
    annotated_path = OUTPUT_DIR / "eval_samples_annotated.json"
    annotated_path.write_text(json.dumps(final, ensure_ascii=False, indent=2))
    print(f"Written: {annotated_path}")


if __name__ == "__main__":
    build_eval_from_db()
