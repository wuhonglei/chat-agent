#!/usr/bin/env python3
"""
Multi-turn QA replay via Kimi WebBridge.

Key difference from single-turn replay:
  - Questions in the same group are sent in the SAME conversation window.
  - Waits for the assistant's response to complete before sending the next turn.
  - Only opens a new conversation between different groups.

Usage:
  python3 replay_multi_turn.py                            # replay all groups
  python3 replay_multi_turn.py --start 1 --end 5         # groups 1-4
  python3 replay_multi_turn.py --dry-run                 # CSV preview only
  python3 replay_multi_turn.py --no-wait-response        # fire-and-forget (don't wait for reply)
"""

import argparse, csv, json, subprocess, sys, time
from pathlib import Path

# ── Config ────────────────────────────────────────────
CHAT_URL = "https://chat.wuhonglei.cn/chat"
CSV_PATH = Path("qa_baseline_20_multi_turn.csv")
SESSION  = "qa-multi-turn-replay"

CFG = {
    "turn_delay": 10,           # seconds between turns in the same group (after response done)
    "group_delay": 5,           # seconds between groups (after new conversation)
    "response_timeout": 180,    # max seconds to wait for assistant response
    "response_poll": 2,         # poll interval for response completion (check button state)
    "nav_wait": 3,              # seconds to wait after navigation
}


# ── WebBridge helpers ─────────────────────────────────
def wb(action: str, args: dict, session: str = SESSION) -> dict:
    payload = json.dumps({"action": action, "args": args, "session": session}, ensure_ascii=False)
    r = subprocess.run(
        ["curl", "-s", "-X", "POST", "http://127.0.0.1:10086/command",
         "-H", "Content-Type: application/json", "-d", payload],
        capture_output=True, text=True, timeout=30,
    )
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return {"ok": False, "error": {"message": r.stdout}}


def ok(r: dict, *, expect_tree: bool = False, expect_evaluate: bool = False) -> bool:
    if not r.get("ok"):
        return False
    if expect_tree or expect_evaluate:
        return bool(r.get("data"))
    return r.get("data", {}).get("success", False)


# ── Chrome activation (macOS) ─────────────────────────
def activate_chrome():
    subprocess.run(["osascript", "-e", 'tell application "Google Chrome" to activate'],
                   capture_output=True)
    time.sleep(2)


# ── CSV loading ───────────────────────────────────────
def load_groups(path: str, start: int, end: int) -> list[dict]:
    """
    Load multi-turn CSV and group by group_id.
    Returns: [{"group_id": 1, "theme": "...", "turns": ["q1", "q2", ...]}, ...]
    """
    raw_groups: dict[int, dict] = {}
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            gid = int(row["group_id"])
            if gid not in raw_groups:
                raw_groups[gid] = {
                    "group_id": gid,
                    "theme": row.get("theme", ""),
                    "turns": [],
                }
            raw_groups[gid]["turns"].append(row["user_question"].strip())

    # Sort by group_id, apply slice
    groups = sorted(raw_groups.values(), key=lambda g: g["group_id"])
    if start > 0 or end >= 0:
        groups = [g for g in groups if g["group_id"] >= start and (end < 0 or g["group_id"] < end)]
    return groups


# ── Core actions ──────────────────────────────────────
def fill_input(question: str) -> bool:
    """Fill textarea via nativeInputValueSetter (React/Ant Design compatible)."""
    q_json = json.dumps(question, ensure_ascii=False)
    code = f"""(() => {{
        const selectors = [
            'textarea.ant-input',
            'textarea[data-testid="chat-input"]',
            'textarea[placeholder*="输入"]',
            'textarea[placeholder*="消息"]',
            'textarea[placeholder*="发送"]',
            'textarea'
        ];
        let t = null;
        for (const sel of selectors) {{ t = document.querySelector(sel); if (t) break; }}
        if (!t) return JSON.stringify({{success:false, error:'no textarea'}});
        t.focus();
        const nativeSet = Object.getOwnPropertyDescriptor(
            window.HTMLTextAreaElement.prototype, 'value').set;
        nativeSet.call(t, {q_json});
        t.dispatchEvent(new Event('input', {{bubbles:true}}));
        t.dispatchEvent(new Event('change', {{bubbles:true}}));
        return JSON.stringify({{success:true, len:t.value.length}});
    }})()"""
    r = wb("evaluate", {"code": code})
    if not ok(r, expect_evaluate=True):
        return False
    try:
        return json.loads(r["data"].get("value", "{}")).get("success", False)
    except (json.JSONDecodeError, KeyError):
        return False


def get_snapshot() -> list | None:
    """Get the accessibility tree snapshot."""
    r = wb("snapshot", {}, SESSION)
    if not ok(r, expect_tree=True):
        return None
    return r["data"].get("tree")


def find_send_button(nodes) -> str | None:
    """Find the send button ref (arrow-up) in the snapshot tree."""
    for n in nodes:
        if isinstance(n, dict):
            if n.get("role") == "button" and n.get("name") == "arrow-up":
                return n.get("ref")
            for c in n.get("children", []):
                r2 = find_send_button([c] if isinstance(c, dict) else c)
                if r2:
                    return r2
        elif isinstance(n, list):
            r2 = find_send_button(n)
            if r2:
                return r2
    return None


def submit_input() -> bool:
    """Get the send button ref and click it."""
    time.sleep(0.3)
    tree = get_snapshot()
    if not tree:
        return False
    ref = find_send_button(tree)
    if ref:
        click_r = wb("click", {"selector": ref}, SESSION)
        return ok(click_r)
    return False


def click_new_conversation() -> bool:
    """Find and click the 'new conversation' button, fallback to navigate /chat."""
    tree = get_snapshot()
    if not tree:
        return False

    def find_ref(nodes, targets):
        for node in nodes:
            if isinstance(node, dict):
                if node.get("name") in targets and node.get("role") == "button":
                    return node.get("ref")
                for child in node.get("children", []):
                    result = find_ref([child], targets)
                    if result:
                        return result
            elif isinstance(node, list):
                result = find_ref(node, targets)
                if result:
                    return result
        return None

    targets = {"开启新对话", "新对话", "新建对话", "New Chat", "New Conversation", "新建"}
    ref = find_ref(tree, targets)
    if ref:
        return ok(wb("click", {"selector": ref}, SESSION))

    # Fallback: navigate
    wb("navigate", {"url": CHAT_URL}, SESSION)
    time.sleep(CFG["nav_wait"])
    return True


def is_response_done() -> bool:
    """
    Check if the assistant has finished responding by inspecting the send button's state.
    - During response: button has NO disabled attribute (it's a stop/square icon).
    - After response:  button HAS disabled="" (it's the arrow-up send icon, disabled because textarea is empty).
    Uses evaluate for a single lightweight DOM check — no snapshot polling needed.
    """
    code = """(() => {
        // Find the primary icon-only button near the input area (the send/stop button)
        const btn = document.querySelector(
            'button.ant-btn-primary.ant-btn-icon-only'
        );
        if (!btn) return JSON.stringify({found: false});
        return JSON.stringify({
            found: true,
            disabled: btn.hasAttribute('disabled'),
            hasArrowUp: !!btn.querySelector('[aria-label="arrow-up"]')
        });
    })()"""
    r = wb("evaluate", {"code": code})
    if not ok(r, expect_evaluate=True):
        return False
    try:
        info = json.loads(r["data"].get("value", "{}"))
        # Response is done when button is disabled AND shows arrow-up icon
        return info.get("found") and info.get("disabled") and info.get("hasArrowUp")
    except (json.JSONDecodeError, KeyError):
        return False


def wait_for_response(timeout: int | None = None) -> bool:
    """
    Wait for the assistant's response to complete.
    Detection: poll the send button's disabled attribute via evaluate.
      - During response: button is NOT disabled (stop icon).
      - After response:  button IS disabled + arrow-up icon.
    Returns True if response completed, False on timeout.
    """
    timeout = timeout or CFG["response_timeout"]
    poll = CFG["response_poll"]

    start_time = time.time()

    # Phase 1: wait for response to start (button should become non-disabled / stop icon)
    while time.time() - start_time < timeout:
        time.sleep(poll)
        if not is_response_done():
            break  # button is no longer the disabled send icon → response started
    else:
        # Timeout: button stayed disabled the whole time (nothing was sent?)
        return False

    # Phase 2: wait for response to finish (button becomes disabled + arrow-up again)
    while time.time() - start_time < timeout:
        time.sleep(poll)
        if is_response_done():
            return True

    return False


# ── Main ──────────────────────────────────────────────
def run(groups: list[dict], dry_run: bool = False, wait_response: bool = True):
    total_groups = len(groups)
    total_turns = sum(len(g["turns"]) for g in groups)

    if dry_run:
        print(f"[dry-run] {total_groups} groups, {total_turns} total turns:")
        for g in groups:
            turns_preview = [q[:50].replace("\n", "\\n") for q in g["turns"]]
            print(f"  Group {g['group_id']:>2}: {g['theme'][:30]:<30} ({len(g['turns'])} turns)")
            for i, tp in enumerate(turns_preview):
                print(f"    Turn {i+1}: {tp}...")
        return

    print("Activating Chrome...")
    activate_chrome()
    wb("navigate", {"url": CHAT_URL, "newTab": True, "group_title": "QA Multi-Turn Replay"})
    time.sleep(CFG["nav_wait"])

    results = []
    turn_counter = 0

    for gi, group in enumerate(groups):
        gid = group["group_id"]
        theme = group["theme"]
        turns = group["turns"]

        print(f"\n{'='*60}")
        print(f"Group {gid}/{total_groups}: {theme} ({len(turns)} turns)")
        print(f"{'='*60}")

        # Start new conversation for each group (except the first one if it's the very start)
        if gi > 0:
            print("  → Opening new conversation...")
            if not click_new_conversation():
                print("  ✗ failed, navigating to /chat")
                wb("navigate", {"url": CHAT_URL}, SESSION)
            time.sleep(CFG["group_delay"])

        for ti, question in enumerate(turns):
            turn_counter += 1
            q_preview = question[:60].replace("\n", "\\n")
            print(f"\n  [{turn_counter}/{total_turns}] Group {gid} Turn {ti+1}/{len(turns)}: {q_preview}...")

            # Fill
            print("    → fill...")
            if not fill_input(question):
                print("    ✗ fill failed, skipping")
                results.append({"group_id": gid, "turn": ti + 1, "status": "fill_failed"})
                continue
            time.sleep(0.3)

            # Submit
            print("    → submit...")
            if not submit_input():
                print("    ✗ submit failed")
                results.append({"group_id": gid, "turn": ti + 1, "status": "submit_failed"})
                continue
            print("    ✓ sent")
            results.append({"group_id": gid, "turn": ti + 1, "status": "sent", "question": q_preview})

            # Wait for response to complete (within same group)
            if wait_response and ti < len(turns) - 1:
                print("    → waiting for response...")
                completed = wait_for_response()
                if completed:
                    print("    ✓ response complete")
                    # Additional delay between turns
                    print(f"    → waiting {CFG['turn_delay']}s before next turn...")
                    time.sleep(CFG["turn_delay"])
                else:
                    print("    ⚠ response timeout, continuing anyway")
                    time.sleep(CFG["turn_delay"])
            elif not wait_response:
                time.sleep(CFG["turn_delay"])
            # Last turn in group: no need to wait for response

    # Summary
    ok_count = sum(1 for r in results if r["status"] == "sent")
    fail_count = total_turns - ok_count
    print(f"\n{'='*60}")
    print(f"Done: {total_groups} groups, {ok_count}/{total_turns} sent, {fail_count} failed")
    print(f"{'='*60}")

    # Save results
    out = Path("replay_multi_turn_results.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"Results saved: {out}")

    wb("close_session", {}, SESSION)
    print("Session closed.")


def main():
    p = argparse.ArgumentParser(description="Multi-turn QA replay via WebBridge")
    p.add_argument("--csv", default=str(CSV_PATH), help="Path to multi-turn CSV")
    p.add_argument("--start", type=int, default=0, help="Start group_id (inclusive)")
    p.add_argument("--end", type=int, default=-1, help="End group_id (exclusive, -1=all)")
    p.add_argument("--turn-delay", type=float, default=CFG["turn_delay"],
                   help="Seconds to wait between turns in the same group (default: 10)")
    p.add_argument("--group-delay", type=float, default=CFG["group_delay"],
                   help="Seconds to wait between groups (default: 5)")
    p.add_argument("--timeout", type=int, default=CFG["response_timeout"],
                   help="Max seconds to wait for assistant response (default: 180)")
    p.add_argument("--no-wait-response", action="store_true",
                   help="Don't wait for response completion (fire-and-forget)")
    p.add_argument("--dry-run", action="store_true", help="Preview only, don't execute")
    args = p.parse_args()

    CFG["turn_delay"] = args.turn_delay
    CFG["group_delay"] = args.group_delay
    CFG["response_timeout"] = args.timeout

    groups = load_groups(args.csv, args.start, args.end)
    if not groups:
        print("No groups found. Check CSV path and group_id range.")
        sys.exit(1)
    print(f"Loaded {len(groups)} groups, {sum(len(g['turns']) for g in groups)} total turns")
    run(groups, dry_run=args.dry_run, wait_response=not args.no_wait_response)


if __name__ == "__main__":
    main()
