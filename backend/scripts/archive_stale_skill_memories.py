"""归档断言 vercel-deploy 存在的陈旧技能记忆（mem0 一次性维护脚本）。

背景：``backend/skills/public/vercel-deploy-claimable`` 已删除（上游 claimable
deploy 接口废弃 + SKILL.md 里的虚拟路径本身就指错，详见会话记录）。但 mem0 线上库
里仍有记忆断言该 skill 存在，会在「网页设计 skill 推荐 / 部署工作流」类提问时被召回，
让模型继续推荐一个不存在的 skill。

本脚本沿用在 dev 库上已验证的 mem0-internals Tier 2 流程：``PUT /memories/{id}``
带 ``metadata.governance_status=archived`` + ``archived_reason``。归档是可逆的
（读接口传 ``include_merged=true`` 仍可见）。

用法：

    # 1) 先干跑（默认行为，只读，不改任何数据）
    MEM0_BASE_URL=http://1.12.53.9:8888 MEM0_API_KEY=m0sk_xxx \\
        uv run python scripts/archive_stale_skill_memories.py

    # 2) 确认输出无误后执行
    MEM0_BASE_URL=... MEM0_API_KEY=... \\
        uv run python scripts/archive_stale_skill_memories.py --apply

    # 3) 回滚（逐条恢复为 active）
    ... --rollback

注意：mem0 的 ``Memory.update`` 会重新 embedding 并刷新 ``updated_at``，而
``updated_at`` 是 decay 的时效信号（见 docs/mem0 与 mem0-internals skill），因此
归档/回滚都会轻微扰动该记忆的 decay 因子。数量少（3 条）可忽略，但不要把它当高频操作。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

USER_ID = "c7d40833-6b26-4696-828f-a94b9de5b47d"

# (memory_id, 必须出现在原文里的片段) —— 片段作为 fail-safe 守卫：
# 库里内容变了就拒绝操作，避免把 id 复用/误配当作目标。
STALE_MEMORIES: tuple[tuple[str, str], ...] = (
    (
        "2d7f2bf5-fb92-4368-ac11-f469a1a20604",
        "13个内置公共skills",
    ),
    (
        "6ce34eed-bc70-4efc-8bbb-bae4500f4b89",
        "使用vercel-deploy部署",
    ),
    (
        "c19f750d-3fca-4241-bfd3-4f1363ecc158",
        "vercel-deploy（用于将网页项目部署到Vercel",
    ),
)

ARCHIVED_REASON = "stale-skill-inventory:vercel-deploy-removed"


def _client() -> tuple[str, str]:
    base = os.environ.get("MEM0_BASE_URL", "").rstrip("/")
    key = os.environ.get("MEM0_API_KEY", "")
    if not base or not key:
        sys.exit(
            "缺少 MEM0_BASE_URL / MEM0_API_KEY 环境变量。"
            "（dev 库地址与 m0sk_ 密钥见会话内存，勿写入仓库）"
        )
    return base, key


def _call(base: str, key: str, path: str, *, method: str = "GET", body: dict | None = None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        base + path,
        data=data,
        method=method,
        headers={
            "X-API-Key": key,
            "Authorization": f"Token {key}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        sys.exit(f"{method} {path} -> HTTP {exc.code}: {exc.read().decode()[:300]}")


def _fetch(base: str, key: str, memory_id: str) -> dict:
    status, payload = _call(base, key, f"/memories/{memory_id}")
    if status != 200 or not isinstance(payload, dict):
        sys.exit(f"读取 {memory_id} 失败: HTTP {status} {str(payload)[:200]}")
    return payload


def _text_of(row: dict) -> str:
    return row.get("memory") or row.get("data") or ""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true", help="真正写入归档标记")
    mode.add_argument("--rollback", action="store_true", help="把状态恢复为 active")
    args = parser.parse_args()

    base, key = _client()
    print(f"mem0: {base}  user_id: {USER_ID}  mode: "
          f"{'apply' if args.apply else 'rollback' if args.rollback else 'dry-run'}")

    targets: list[tuple[str, str, dict]] = []
    for memory_id, guard in STALE_MEMORIES:
        row = _fetch(base, key, memory_id)
        text = _text_of(row)
        gov = (row.get("metadata") or {}).get("governance_status")
        ok = guard in text
        print(f"\n--- {memory_id}  governance_status={gov}  guard={'OK' if ok else 'MISS'}")
        print(f"    {text[:200]}")
        if not ok:
            print("    跳过：守卫片段未命中，库内容与脚本预期不一致，先人工核对。")
            continue
        if "vercel-deploy" not in text:
            print("    跳过：正文已不含 vercel-deploy，无需处理。")
            continue
        targets.append((memory_id, text, row.get("metadata") or {}))

    if not targets:
        print("\n没有需要处理的目标。")
        return 0

    if not args.apply and not args.rollback:
        print(f"\n[dry-run] 将对 {len(targets)} 条执行：")
        for memory_id, _, _ in targets:
            print(f"    {memory_id}")
        print("\n加 --apply 执行归档；归档后可用 --rollback 恢复。")
        return 0

    if args.rollback:
        metadata = {"governance_status": "active"}
        action = "恢复 active"
    else:
        metadata = {"governance_status": "archived", "archived_reason": ARCHIVED_REASON}
        action = f"归档 (reason={ARCHIVED_REASON})"

    for memory_id, _, _ in targets:
        status, payload = _call(
            base, key, f"/memories/{memory_id}", method="PUT", body={"metadata": metadata}
        )
        print(f"\n{memory_id} -> HTTP {status} {action}")
        if status != 200:
            sys.exit(f"写入失败: {str(payload)[:300]}")

    print("\n回读校验：")
    for memory_id, _, _ in targets:
        row = _fetch(base, key, memory_id)
        gov = (row.get("metadata") or {}).get("governance_status")
        print(f"    {memory_id}  governance_status={gov}")

    print("\n建议再做一次污染查询（不带 include_merged）：")
    print('    POST /search {"query": "推荐网页设计的 skill", "filters": {"user_id": "%s"},'
          ' "top_k": 5}' % USER_ID)
    print("    期望：vercel-deploy 不再出现在结果里；带 \"include_merged\": true 时应重新可见（可逆性验证）。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
