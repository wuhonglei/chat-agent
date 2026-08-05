"""通过 Langfuse API 补充 eval 集的 memory-search 数据。

用法:
    python scripts/eval_memory_supplement.py
"""

import json
import re
import time
from datetime import datetime, timedelta
from pathlib import Path

import httpx

# Langfuse public API
with open(Path(__file__).parent / "extract_tool_context.py") as f:
    content = f.read()
    match = re.search(r'AUTH = "(.+?)"', content)
    auth_str = match.group(1)
    parts = auth_str.split(":")
    PK, SK = parts[0], parts[1]

HOST = "https://langfuse.wuhonglei.cn"
PROJECT_ID = "cmpwh4pcg0002qn07mv4f20af"

# Session cookie (from browser)
SESSION_COOKIE = None

EVAL_PATH = Path(__file__).parent.parent / "data" / "eval_set" / "v1.0" / "eval_samples_annotated.json"


def get_session_cookie():
    """从浏览器获取 session cookie（需要手动提供）。"""
    global SESSION_COOKIE
    if SESSION_COOKIE:
        return SESSION_COOKIE
    # Try to read from env or prompt
    import os
    SESSION_COOKIE = os.environ.get("LANGFUSE_SESSION_COOKIE")
    if not SESSION_COOKIE:
        raise RuntimeError("请设置 LANGFUSE_SESSION_COOKIE 环境变量")
    return SESSION_COOKIE


def fetch_memory_observations(trace_ids: set[str]) -> dict[str, list[dict]]:
    """从 Langfuse 获取所有 memory-search observations。"""
    result = {}
    from_time = (datetime.utcnow() - timedelta(days=90)).isoformat() + "Z"
    to_time = datetime.utcnow().isoformat() + "Z"

    resp = httpx.get(
        f"{HOST}/api/public/v2/observations",
        auth=(PK, SK),
        params={
            "fromStartTime": from_time,
            "toStartTime": to_time,
            "name": "memory-search",
            "limit": 500,
        },
        timeout=30,
    )
    data = resp.json()
    obs = data.get("data", [])

    for o in obs:
        tid = o.get("traceId", "")
        if tid in trace_ids:
            if tid not in result:
                result[tid] = []
            result[tid].append({"id": o["id"], "startTime": o.get("startTime")})

    return result


def fetch_memory_detail(trace_id: str, observation_id: str, start_time: str) -> dict | None:
    """通过 tRPC 端点获取 memory-search 的详细数据。"""
    cookie = get_session_cookie()
    url = f"{HOST}/api/trpc/events.batchIO"
    cookies = {"next-auth.session-token": cookie}

    payload = {
        "json": {
            "projectId": PROJECT_ID,
            "traceId": trace_id,
            "observations": [{"id": observation_id, "traceId": trace_id}],
            "minStartTime": start_time,
            "maxStartTime": start_time,
            "truncated": False,
        },
        "meta": {
            "values": {"minStartTime": ["Date"], "maxStartTime": ["Date"]},
            "referentialEqualities": {"minStartTime": ["maxStartTime"]},
        },
    }

    try:
        resp = httpx.post(url, cookies=cookies, json=payload, timeout=15)
        if resp.status_code != 200:
            return None

        data = resp.json()
        observations = data.get("result", {}).get("data", {}).get("json", [])
        if not observations:
            return None

        obs = observations[0]
        output = obs.get("output", "")
        if not output:
            return None

        return json.loads(output) if isinstance(output, str) else output
    except Exception as e:
        print(f"    Error: {e}")
        return None


def format_memories(memory_data: dict) -> str | None:
    """格式化 memory 数据为可读字符串。"""
    memories = memory_data.get("memories", [])
    if not memories:
        return None

    lines = []
    for m in memories:
        memory_text = m.get("memory", "")
        score = m.get("score", 0)
        lines.append(f"- {memory_text} (score: {score:.2f})")

    return "<memories>\n" + "\n".join(lines) + "\n</memories>"


def main():
    # Load eval data
    with open(EVAL_PATH) as f:
        data = json.load(f)

    print(f"Loaded {len(data)} items")

    # Get all trace_ids
    trace_ids = {item["trace_id"] for item in data}

    # Find memory-search observations
    print("Fetching memory-search observations...")
    memory_obs = fetch_memory_observations(trace_ids)
    print(f"Found memory-search for {len(memory_obs)} traces")

    if not memory_obs:
        print("No memory-search observations found")
        return

    # Fetch details for each
    updated = 0
    errors = 0

    for item in data:
        tid = item["trace_id"]
        if tid not in memory_obs:
            continue

        obs_list = memory_obs[tid]
        if not obs_list:
            continue

        # Use the first memory-search observation
        obs = obs_list[0]
        memory_data = fetch_memory_detail(tid, obs["id"], obs["startTime"])

        if not memory_data:
            errors += 1
            continue

        memories_str = format_memories(memory_data)
        if not memories_str:
            continue

        # Prepend memories to context
        old_ctx = item.get("context") or ""
        if "<memories>" in old_ctx:
            continue  # Already has memories

        item["context"] = memories_str + "\n\n" + old_ctx if old_ctx else memories_str
        updated += 1
        print(f"  [{updated}] {item['query'][:40]}... added memories")

        time.sleep(0.5)

    # Save
    with open(EVAL_PATH, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\nDone! Updated: {updated}, Errors: {errors}")


if __name__ == "__main__":
    main()
