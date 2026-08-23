"""拉取 Langfuse dataset，将 ground_truth_points 更新为带权重格式。

用法:
    uv run python scripts/update_ground_truth_weights.py [--dry-run] [--limit N]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

# 加载 .env
_env_path = Path(__file__).resolve().parent.parent / ".env"
if _env_path.exists():
    for _line in _env_path.read_text().splitlines():
        if "=" in _line and not _line.strip().startswith("#"):
            _k, _v = _line.split("=", 1)
            _k, _v = _k.strip(), _v.strip().strip('"').strip("'")
            if _k:
                os.environ.setdefault(_k, _v)

import httpx
from langfuse import Langfuse

DATASET_NAME = "chat-agent-eval"

DASHSCOPE_API_BASE = os.environ.get(
    "DASHSCOPE_API_BASE", "https://dashscope.aliyuncs.com/compatible-mode/v1"
)
DASHSCOPE_API_KEY = os.environ.get("DASHSCOPE_API_KEY", "")
DASHSCOPE_MODEL = os.environ.get("DASHSCOPE_MODEL", "qwen3.8-max")

CLASSIFY_PROMPT = """你是一个评估要点分类器。根据用户问题，将每个要点分类为核心要点或补充要点。

规则：
- core（核心要点）：直接回答用户问题所必需的信息。用户问"房租多少"，金额就是核心。
- supplementary（补充要点）：能让回答更完整但非必须的信息。用户问"房租多少"，位置、面积是补充。
- 简单事实性问题（问时间/地点/金额/名称等）通常只有 1-2 个核心要点
- 复杂问题（如何做/为什么/对比）核心要点会更多

输入：用户问题和要点列表，JSON 格式
输出：JSON 数组，每个元素 {"text": "要点文本", "weight": "core" 或 "supplementary"}

示例输入：
{"query": "房租一个月多少", "points": ["房租金额及支付方式", "租房位置和房屋类型", "房屋面积及房间数量"]}

示例输出：
[{"text": "房租金额及支付方式", "weight": "core"}, {"text": "租房位置和房屋类型", "weight": "supplementary"}, {"text": "房屋面积及房间数量", "weight": "supplementary"}]"""


def classify_points(query: str, points: list[str]) -> list[dict]:
    """调用 LLM 将要点分类为核心/补充。"""
    if not DASHSCOPE_API_KEY:
        raise RuntimeError("未找到 DASHSCOPE_API_KEY")
    user_input = json.dumps({"query": query, "points": points}, ensure_ascii=False)
    resp = httpx.post(
        f"{DASHSCOPE_API_BASE}/chat/completions",
        headers={
            "Authorization": f"Bearer {DASHSCOPE_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": DASHSCOPE_MODEL,
            "messages": [
                {"role": "system", "content": CLASSIFY_PROMPT},
                {"role": "user", "content": user_input},
            ],
            "temperature": 0,
            "max_tokens": 2000,
            "enable_thinking": False,
        },
        timeout=60,
    )
    resp.raise_for_status()
    raw = resp.json()["choices"][0]["message"]["content"]
    try:
        if "[" in raw:
            json_str = raw[raw.index("[") : raw.rindex("]") + 1]
            result = json.loads(json_str)
            # 验证格式
            if all(isinstance(r, dict) and "text" in r and "weight" in r for r in result):
                return result
    except (json.JSONDecodeError, ValueError):
        pass
    # fallback: 全部标记为 core
    return [{"text": p, "weight": "core"} for p in points]


def main():
    parser = argparse.ArgumentParser(description="更新 Langfuse dataset ground_truth_points 权重")
    parser.add_argument("--dry-run", action="store_true", help="只打印不更新")
    parser.add_argument("--limit", type=int, default=0, help="限制处理条数（0=全部）")
    args = parser.parse_args()

    client = Langfuse()
    dataset = client.get_dataset(DATASET_NAME)
    items = dataset.items
    total = len(items)
    print(f"Dataset '{DATASET_NAME}' 共 {total} 条")

    if args.limit > 0:
        items = items[: args.limit]
        print(f"限制处理前 {args.limit} 条")

    updated = 0
    skipped = 0
    errors = 0

    for i, item in enumerate(items):
        metadata = item.metadata or {}
        annotation = metadata.get("annotation", {})
        gt_points = annotation.get("ground_truth_points", [])

        if not gt_points:
            print(f"  [{i+1}/{len(items)}] {item.id[:12]}... 无 ground_truth_points，跳过")
            skipped += 1
            continue

        # 已经是带权重格式则跳过
        if gt_points and isinstance(gt_points[0], dict) and "weight" in gt_points[0]:
            print(f"  [{i+1}/{len(items)}] {item.id[:12]}... 已有权重，跳过")
            skipped += 1
            continue

        # 从 input 中提取 query
        item_input = item.input if isinstance(item.input, dict) else {}
        query = ""
        messages = item_input.get("messages", [])
        for msg in messages:
            if isinstance(msg, dict) and msg.get("role") == "user":
                query = msg.get("content", "").strip()
                break
        if not query:
            query = str(item_input.get("query", ""))[:200]

        print(f"  [{i+1}/{len(items)}] {item.id[:12]}... query={query[:50]}... points={len(gt_points)}")

        try:
            weighted_points = classify_points(query, gt_points)
            core_count = sum(1 for p in weighted_points if p.get("weight") == "core")
            sup_count = sum(1 for p in weighted_points if p.get("weight") == "supplementary")
            print(f"    → core={core_count}, supplementary={sup_count}")

            if not args.dry_run:
                # 更新 metadata
                new_metadata = dict(metadata)
                new_annotation = dict(annotation)
                new_annotation["ground_truth_points"] = weighted_points
                new_metadata["annotation"] = new_annotation

                # Langfuse SDK: create_dataset_item 传已有 id 即为更新
                client.create_dataset_item(
                    dataset_name=DATASET_NAME,
                    id=item.id,
                    input=item.input,
                    expected_output=item.expected_output,
                    metadata=new_metadata,
                )
                updated += 1
                print(f"    → 已更新")
            else:
                print(f"    → [dry-run] 跳过更新")

            # 避免限流
            time.sleep(0.5)

        except Exception as e:
            print(f"    → 错误: {e}")
            errors += 1

    print(f"\n完成: 更新 {updated}, 跳过 {skipped}, 错误 {errors}")


if __name__ == "__main__":
    main()
