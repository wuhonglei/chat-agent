"""批量提取 trace 的工具调用结果作为 context。

针对有工具调用（web search / code execute / file read）但缺少 context 的 trace，
从 Langfuse observations 中提取工具输出，补充到 eval_samples.json 和 eval_samples_annotated.json。

用法:
    uv run python scripts/extract_tool_context.py
"""

import json
import subprocess
from pathlib import Path

AUTH = "pk-lf-26ef9e82-6509-46b4-a4e7-33b1e496d3ae:sk-lf-fabdfda1-7803-4442-9908-065963106875"
HOST = "https://langfuse.wuhonglei.cn"

EVAL_PATH = Path(__file__).resolve().parent.parent / "data" / "eval_set" / "v1.0" / "eval_samples.json"
ANNOTATED_PATH = Path(__file__).resolve().parent.parent / "data" / "eval_set" / "v1.0" / "eval_samples_annotated.json"

# 需要提取 context 的工具类型
CONTEXT_TOOLS = {
    "tavily_web_search",
    "tavily_web_pages_extract",
    "code_execute_code",
    "zread_read_file",
    "zread_get_repo_structure",
    "zread_search_doc",
    "file_present_files",
}


def fetch_observations(trace_id: str) -> list[dict]:
    """获取 trace 的所有 observations。"""
    try:
        r = subprocess.run(
            ["curl", "-s", "-u", AUTH,
             f"{HOST}/api/public/observations?traceId={trace_id}&limit=50",
             "--connect-timeout", "10", "--max-time", "20"],
            capture_output=True, text=True, timeout=25,
        )
        return json.loads(r.stdout).get("data", [])
    except Exception:
        return []


def extract_context_from_tools(observations: list[dict]) -> str | None:
    """从工具调用结果中提取 context。"""
    context_parts = []

    for obs in observations:
        if obs.get("type") != "TOOL":
            continue
        name = obs.get("name", "")
        if name not in CONTEXT_TOOLS:
            continue

        output = obs.get("output", "")
        if not output:
            continue

        # 截断过长的输出
        max_len = 3000
        truncated = output[:max_len] + ("..." if len(output) > max_len else "")
        context_parts.append(f"### 工具: {name}\n{truncated}")

    if not context_parts:
        return None
    return "\n\n".join(context_parts)


def update_eval_items(items: list[dict], context_map: dict[str, str]) -> int:
    """更新 eval items 的 context 字段。"""
    updated = 0
    for item in items:
        tid = item["trace_id"]
        if not item.get("context") and tid in context_map:
            item["context"] = context_map[tid]
            updated += 1
    return updated


def main():
    # 读取数据
    eval_items = json.loads(EVAL_PATH.read_text())
    annotated_items = json.loads(ANNOTATED_PATH.read_text()) if ANNOTATED_PATH.exists() else []

    # 找出无 context 的 trace
    no_context = [item for item in eval_items if not item.get("context")]
    print(f"Total: {len(eval_items)}, No context: {len(no_context)}")

    # 批量提取 context
    context_map: dict[str, str] = {}
    extracted = 0
    skipped = 0

    for i, item in enumerate(no_context):
        tid = item["trace_id"]
        observations = fetch_observations(tid)

        # 检查是否有目标工具调用
        has_tools = any(
            obs.get("type") == "TOOL" and obs.get("name", "") in CONTEXT_TOOLS
            for obs in observations
        )

        if not has_tools:
            skipped += 1
            continue

        context = extract_context_from_tools(observations)
        if context:
            context_map[tid] = context
            extracted += 1
            print(f"  [{i+1}/{len(no_context)}] {tid[:12]}... extracted ({len(context)} chars)")
        else:
            skipped += 1

    print(f"\nExtracted: {extracted}, Skipped: {skipped}")

    # 更新两个文件
    updated_eval = update_eval_items(eval_items, context_map)
    EVAL_PATH.write_text(json.dumps(eval_items, ensure_ascii=False, indent=2))
    print(f"Updated eval_samples.json: {updated_eval} items")

    if annotated_items:
        updated_annotated = update_eval_items(annotated_items, context_map)
        ANNOTATED_PATH.write_text(json.dumps(annotated_items, ensure_ascii=False, indent=2))
        print(f"Updated eval_samples_annotated.json: {updated_annotated} items")


if __name__ == "__main__":
    main()
