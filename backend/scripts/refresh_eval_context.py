"""重新生成 context（去掉 3000 截断），对比变化项并重新标注。

用法:
    DATABASE__HOST=134.175.182.235 DASHSCOPE_API_KEY=xxx uv run python scripts/refresh_eval_context.py
"""

import json
import os
import subprocess
import time
from pathlib import Path

import httpx
from sqlalchemy import text

from app.core.db import get_db

ANNOTATED_PATH = (
    Path(__file__).resolve().parent.parent
    / "data"
    / "eval_set"
    / "v1.0"
    / "eval_samples_annotated.json"
)
API_BASE_LLM = "https://dashscope.aliyuncs.com/compatible-mode/v1"
API_BASE_FILES = "https://chat.wuhonglei.cn"
MODEL = "qwen-plus"

# 附件跳过类型
SKIP_TYPES = {"text", "tool_result", "image"}


def get_api_key() -> str:
    key = os.environ.get("DASHSCOPE_API_KEY")
    if not key:
        env_path = Path(__file__).resolve().parent.parent / ".env"
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                if line.startswith("DASHSCOPE_API_KEY="):
                    key = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break
    if not key:
        raise RuntimeError("未找到 DASHSCOPE_API_KEY")
    return key


def fetch_derived_markdown(url: str) -> str | None:
    full_url = f"{API_BASE_FILES}{url}"
    try:
        r = subprocess.run(
            ["curl", "-s", "--connect-timeout", "10", "--max-time", "30", full_url],
            capture_output=True, text=True, timeout=35,
        )
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout
    except Exception:
        pass
    return None


def extract_attachment_context(blocks: list[dict]) -> str | None:
    parts = []
    for block in blocks:
        btype = block.get("type", "")
        if btype in SKIP_TYPES:
            continue
        name = block.get("name", "")
        size = block.get("size", 0)
        mime = block.get("mime", "")
        md = block.get("markdown")

        desc_lines = [f"文件名: {name}", f"类型: {btype} ({mime})", f"大小: {size} bytes"]
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

        if md and md.get("url"):
            content = fetch_derived_markdown(md["url"])
            if content:
                parts.append(content)

    if not parts:
        return None
    return "<attachment>\n" + "\n\n".join(parts) + "\n</attachment>"


def rebuild_context(conversation_id: str, session) -> str | None:
    """从 DB 重新构建 context（无截断）。"""
    result = session.execute(
        text("""
            SELECT role, content_blocks, created_at, status
            FROM messages
            WHERE conversation_id = :cid
            ORDER BY created_at ASC
        """),
        {"cid": conversation_id},
    )
    messages = list(result)
    if not messages:
        return None

    # 找首条 user
    first_user_idx = None
    for i, (role, blocks, _, _) in enumerate(messages):
        if role == "user" and blocks:
            for b in blocks:
                if b.get("type") == "text" and b.get("text", "").strip():
                    first_user_idx = i
                    break
            if first_user_idx is not None:
                break

    if first_user_idx is None:
        return None

    context_parts = []

    # 首条 assistant 的 tool_result（无截断）
    for role, blocks, _, _ in messages[first_user_idx + 1 :]:
        if role != "assistant" or not blocks:
            continue
        for block in blocks:
            if block.get("type") == "tool_result":
                content = block.get("content", "")
                if content:
                    context_parts.append(f"<tool>\n{content}\n</tool>")
        break

    # 首条 user 的附件
    first_user_blocks = messages[first_user_idx][1]
    if first_user_blocks:
        att_ctx = extract_attachment_context(first_user_blocks)
        if att_ctx:
            context_parts.append(att_ctx)

    if not context_parts:
        return None
    return "\n\n".join(context_parts)


SYSTEM_STEP1 = """你是一个评估集标注助手。根据用户的问题，列出一个好的回答应该包含的要点。

规则：
- 每个要点一句话，2-5 个要点
- 要点是「该覆盖哪些方面」，不是具体答案
- 输出 JSON 数组格式

示例输入：住三亚海棠湾中午如何吃饭
示例输出：
["用餐地点分类（酒店内/美食街/周边餐厅）", "各方案的价格区间", "营业时间（中午是否营业）", "交通方式或距离", "是否需要预约"]"""

SYSTEM_STEP2 = """你是一个回答质量评估器。根据用户问题、标准要点、模型回答，打两个分。

## 重要规则

1. 如果输入中包含【参考资料/工具返回内容】，这些内容是从知识库、搜索引擎、用户附件中获取的真实数据。模型回答是基于这些参考资料生成的。评分时必须以参考资料为事实依据，不要用你自身的知识判断事实性。
2. 如果参考资料中确认了某个信息（如日期、金额、名称），模型回答中包含该信息就是正确的，不是虚构。
3. 只有当模型回答中的信息既不在参考资料中，也无法从参考资料推导出来时，才能判定为「虚构」。

## 评分标准

correctness_score（准确性，1-5）：回答中说的内容是否正确
  5=完全正确 4=基本正确有小瑕疵 3=部分正确有明显错误 2=大部分错误 1=完全错误
  注意：有参考资料时，以参考资料为准判断正确性；无参考资料时，以常识和逻辑判断。

completeness_score（完整性，1-5）：回答是否覆盖了标准要点
  5=覆盖率>=90% 4=覆盖率>=70% 3=覆盖率>=50% 2=覆盖率<50% 1=几乎未覆盖

scene_tag（场景标签）：qa=知识问答 rag=检索回答 tool=工具调用 chat=闲聊创意

输出 JSON：
{"correctness_score": N, "completeness_score": N, "scene_tag": "...", "notes": "扣分原因简述"}"""


def call_llm(api_key: str, system: str, user: str) -> str:
    resp = httpx.post(
        f"{API_BASE_LLM}/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": MODEL,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0,
            "max_tokens": 1000,
        },
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def annotate_one(api_key: str, item: dict) -> dict:
    query = item.get("query", "")
    answer = item.get("answer", "")

    points_raw = call_llm(api_key, SYSTEM_STEP1, query)
    try:
        if "[" in points_raw:
            json_str = points_raw[points_raw.index("[") : points_raw.rindex("]") + 1]
            ground_truth_points = json.loads(json_str)
        else:
            ground_truth_points = [p.strip() for p in points_raw.strip().split("\n") if p.strip()]
    except (json.JSONDecodeError, ValueError):
        ground_truth_points = [points_raw.strip()]

    context = item.get("context", "")
    context_section = f"\n\n【参考资料/工具返回内容】\n{context}" if context else ""
    score_input = (
        f"【用户问题】{query}\n\n【标准要点】\n"
        + "\n".join(f"- {p}" for p in ground_truth_points)
        + context_section
        + f"\n\n【模型回答】\n{answer[:4000]}"
    )
    score_raw = call_llm(api_key, SYSTEM_STEP2, score_input)
    try:
        if "{" in score_raw:
            json_str = score_raw[score_raw.index("{") : score_raw.rindex("}") + 1]
            scores = json.loads(json_str)
        else:
            scores = {}
    except (json.JSONDecodeError, ValueError):
        scores = {}

    return {
        "ground_truth_points": ground_truth_points,
        "scene_tag": scores.get("scene_tag", ""),
        "correctness_score": scores.get("correctness_score"),
        "completeness_score": scores.get("completeness_score"),
        "notes": scores.get("notes", ""),
        "_auto_annotated": True,
    }


def main():
    api_key = get_api_key()
    session = next(get_db())

    items = json.loads(ANNOTATED_PATH.read_text())
    print(f"Loaded {len(items)} items")

    updated = 0
    skipped = 0
    errors = 0

    for i, item in enumerate(items):
        tid = item["trace_id"]
        old_ctx = item.get("context") or ""
        new_ctx = rebuild_context(tid, session) or ""

        if old_ctx == new_ctx:
            skipped += 1
            continue

        # context 变化，更新并重新标注
        print(f"  [{i+1}/{len(items)}] {tid[:12]}... context changed ({len(old_ctx)} -> {len(new_ctx)} chars)")
        item["context"] = new_ctx or None

        try:
            item["annotation"] = annotate_one(api_key, item)
            updated += 1
            print(f"    ✓ re-annotated")
        except Exception as e:
            errors += 1
            print(f"    ✗ annotate error: {e}")

        # 每 5 条保存一次
        if updated % 5 == 0:
            ANNOTATED_PATH.write_text(json.dumps(items, ensure_ascii=False, indent=2))
        time.sleep(1)

    # 最终保存
    ANNOTATED_PATH.write_text(json.dumps(items, ensure_ascii=False, indent=2))
    print(f"\nDone! Updated: {updated}, Skipped: {skipped}, Errors: {errors}")


if __name__ == "__main__":
    main()
