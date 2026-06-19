#!/usr/bin/env python3
"""
从 qa_classification.csv 中按同分布挑选 100 个问题。
使用 LLM (mimo-v2.5-pro) 确保多样性和代表性。
"""

import csv
import json
import os
import random
import sys
import time
import requests
from collections import defaultdict

from nacos_config import get_provider_credentials, load_nacos_config

# --- Config ---
INPUT_CSV = os.path.join(os.path.dirname(__file__), "qa_classification.csv")
OUTPUT_CSV = os.path.join(os.path.dirname(__file__), "qa_baseline_100.csv")

_nacos = load_nacos_config(prod=True)
_xiaomi = get_provider_credentials(_nacos, "xiaomi")
API_KEY = _xiaomi.get("api_key") or os.environ.get("XIAOMI_API_KEY", "")
BASE_URL = _xiaomi.get("api_base") or os.environ.get(
    "XIAOMI_BASE_URL", "https://token-plan-cn.xiaomimimo.com/v1"
)
API_URL = f"{BASE_URL.rstrip('/')}/chat/completions"
MODEL = "mimo-v2.5-pro"

TARGETS = {"simple_chat": 59, "single_tool": 31, "multi_tool": 10}


def load_data():
    """Load and filter CSV to 3 categories."""
    with open(INPUT_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = [r for r in reader if r["category"] in TARGETS]
    return rows


def group_by_category(rows):
    groups = defaultdict(list)
    for r in rows:
        groups[r["category"]].append(r)
    return groups


def llm_select(category, candidates, target_count, batch_hint=""):
    """Ask LLM to pick `target_count` most diverse/representative questions."""
    # Build numbered list
    lines = []
    for i, c in enumerate(candidates):
        lines.append(f"{i+1}. {c['user_question']}")
    question_list = "\n".join(lines)

    # Ask for a few extra to have margin
    ask_count = target_count + 5
    prompt = f"""你是一个数据集采样专家。下面是一个 AI 聊天产品中用户真实提问列表，类别为 "{category}"。

请从以下 {len(candidates)} 个问题中，挑选 {ask_count} 个最具**多样性和代表性**的问题，覆盖尽可能多的不同话题、场景和提问风格。
{batch_hint}

要求：
1. 只输出被选中问题的编号，用英文逗号分隔，不要输出任何其他文字。
2. 例如：1,5,12,23,45
3. 必须恰好选 {ask_count} 个，不多不少。

问题列表：
{question_list}"""

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }
    body = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
        "max_tokens": 4096,
    }

    for attempt in range(5):
        try:
            resp = requests.post(API_URL, headers=headers, json=body, timeout=120)
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"].strip()
            # Parse numbers
            nums = []
            for part in content.replace("\n", ",").split(","):
                part = part.strip().strip(".")
                if part.isdigit():
                    nums.append(int(part))
            # De-duplicate and cap
            seen = set()
            unique = []
            for n in nums:
                if n not in seen and 1 <= n <= len(candidates):
                    seen.add(n)
                    unique.append(n)
            if len(unique) >= target_count:
                return unique[:target_count]
            print(f"  [warn] attempt {attempt+1}: got {len(unique)} unique valid indices (raw: {len(nums)}), need {target_count}. Retrying...", file=sys.stderr)
            # Debug: show raw content
            print(f"  [debug] raw content: {content[:200]}", file=sys.stderr)
        except Exception as e:
            print(f"  [error] attempt {attempt+1}: {e}", file=sys.stderr)
        time.sleep(2)

    # Fallback: random
    print(f"  [fallback] random selection for {category}", file=sys.stderr)
    return random.sample(range(1, len(candidates) + 1), target_count)


def main():
    if not API_KEY:
        print("Error: XIAOMI_API_KEY not set in nacos config or XIAOMI_API_KEY env var", file=sys.stderr)
        sys.exit(1)

    rows = load_data()
    groups = group_by_category(rows)
    selected_rows = []

    for cat in ["simple_chat", "single_tool", "multi_tool"]:
        target = TARGETS[cat]
        candidates = groups[cat]
        print(f"\n=== {cat}: {len(candidates)} candidates -> select {target} ===")

        # If candidates <= target, take all
        if len(candidates) <= target:
            print(f"  Taking all {len(candidates)}")
            selected_rows.extend(candidates)
            continue

        # For large categories, pre-sample to reduce token usage
        # but keep enough margin for LLM to exercise choice
        if len(candidates) > 80:
            pre_sample = random.sample(candidates, 80)
            hint = f"（注：这些是从更大池中随机抽取的子集）"
            print(f"  Pre-sampled 80 from {len(candidates)} to reduce tokens")
        else:
            pre_sample = candidates
            hint = ""

        indices = llm_select(cat, pre_sample, target, hint)
        print(f"  LLM selected indices: {indices}")

        for idx in indices:
            selected_rows.append(pre_sample[idx - 1])

    # Write output
    fieldnames = list(selected_rows[0].keys())
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(selected_rows)

    print(f"\n=== Done ===")
    print(f"Selected {len(selected_rows)} questions -> {OUTPUT_CSV}")
    from collections import Counter
    final_dist = Counter(r["category"] for r in selected_rows)
    for cat in ["simple_chat", "single_tool", "multi_tool"]:
        print(f"  {cat}: {final_dist[cat]}")


if __name__ == "__main__":
    main()
