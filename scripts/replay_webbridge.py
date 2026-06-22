#!/usr/bin/env python3
"""
Batch QA replay via Kimi WebBridge.
Flow: open chat → fill question → Enter → wait for response → click "新对话" → repeat.

Usage:
  python3 replay_webbridge.py                     # replay all
  python3 replay_webbridge.py --start 0 --end 10  # replay rows 0-9
  python3 replay_webbridge.py --dry-run            # CSV preview only
"""

import argparse, csv, json, subprocess, sys, time
from pathlib import Path

# ── Config ────────────────────────────────────────────
CHAT_URL = "https://chat.wuhonglei.cn/chat"
CSV_PATH = Path(__file__).parent / "qa_baseline_100.csv"
SESSION  = "qa-replay"

CFG = {"delay_between": 5, "response_timeout": 90, "poll_interval": 2, "nav_wait": 2}


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
def load_questions(path: str, start: int, end: int) -> list[str]:
    questions = []
    with open(path, newline="", encoding="utf-8") as f:
        for i, row in enumerate(csv.DictReader(f)):
            if i < start:
                continue
            if end >= 0 and i >= end:
                break
            q = row.get("user_question", "").strip()
            if q:
                questions.append(q)
    return questions


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


def submit_input() -> bool:
    """Get the send button ref and click it."""
    time.sleep(0.3)
    r = wb("snapshot", {}, SESSION)
    if not ok(r, expect_tree=True):
        return False

    def find_send(nodes):
        for n in nodes:
            if isinstance(n, dict):
                if n.get("role") == "button" and n.get("name") == "arrow-up":
                    return n.get("ref")
                for c in n.get("children", []):
                    r2 = find_send([c] if isinstance(c, dict) else c)
                    if r2:
                        return r2
            elif isinstance(n, list):
                r2 = find_send(n)
                if r2:
                    return r2
        return None

    ref = find_send(r["data"]["tree"])
    if ref:
        click_r = wb("click", {"selector": ref}, SESSION)
        return ok(click_r)
    return False


def wait_for_response(timeout: int | None = None) -> dict:
    """Poll snapshot until tree length stabilizes (universal completion detection)."""
    timeout = timeout or CFG["response_timeout"]
    start, last_len, stable = time.time(), 0, 0

    while time.time() - start < timeout:
        time.sleep(CFG["poll_interval"])
        r = wb("snapshot", {}, SESSION)
        if not ok(r, expect_tree=True):
            err = r.get("error", {}).get("message", "")
            if "no tab" in err or "closed" in err:
                return {"success": False, "error": "tab_lost"}
            continue

        tree_str = json.dumps(r["data"]["tree"], ensure_ascii=False)
        cur_len = len(tree_str)

        if cur_len > 500 and cur_len == last_len:
            stable += 1
            if stable >= 2:
                return {"success": True, "elapsed": round(time.time() - start, 1)}
        else:
            stable = 0
        last_len = cur_len

    return {"success": False, "error": "timeout"}


def click_new_conversation() -> bool:
    """Find and click the 'new conversation' button, fallback to navigate /chat."""
    r = wb("snapshot", {}, SESSION)
    if not ok(r, expect_tree=True):
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
    ref = find_ref(r["data"]["tree"], targets)
    if ref:
        return ok(wb("click", {"selector": ref}, SESSION))

    # Fallback
    wb("navigate", {"url": CHAT_URL}, SESSION)
    time.sleep(CFG["nav_wait"])
    return True


def is_tab_lost(r: dict) -> bool:
    err = r.get("error", {}).get("message", "")
    return "no tab" in err or "closed" in err


# ── Main ──────────────────────────────────────────────
def run(questions: list[str], dry_run: bool = False):
    total = len(questions)
    if dry_run:
        print(f"[dry-run] {total} questions. First 3:")
        for i, q in enumerate(questions[:3]):
            nl = "\\n"
            print(f"  [{i}] {q[:80].replace(chr(10), nl)}...")
        return

    # Activate Chrome + open initial tab
    print("Activating Chrome...")
    activate_chrome()
    wb("navigate", {"url": CHAT_URL, "newTab": True, "group_title": "QA Replay"})
    time.sleep(CFG["nav_wait"])

    results = []
    for i, question in enumerate(questions):
        q_preview = question[:60].replace("\n", "\\n")
        print(f"\n[{i+1}/{total}] {q_preview}...")

        if i > 0:
            print("  → new conversation...")
            if not click_new_conversation():
                print("  ✗ failed, navigating to /chat")
                wb("navigate", {"url": CHAT_URL}, SESSION)
            time.sleep(CFG["nav_wait"])

        print("  → fill...")
        if not fill_input(question):
            print("  ✗ fill failed, skipping")
            results.append({"index": i, "status": "fill_failed"})
            continue
        time.sleep(0.3)

        print("  → submit...")
        if not submit_input():
            print("  ✗ submit failed")
            results.append({"index": i, "status": "submit_failed"})
            continue
        print(" ✓ sent")
        results.append({"index": i, "status": "sent"})

        time.sleep(CFG["delay_between"])

    # Summary
    ok_count = sum(1 for r in results if r["status"] in ("ok", "sent"))
    times = [r["elapsed"] for r in results if "elapsed" in r]
    avg = round(sum(times) / len(times), 1) if times else 0

    print(f"\n{'='*50}")
    print(f"Done: {ok_count}/{total} ok, {total - ok_count} failed")
    print(f"Avg response: {avg}s")

    out = Path(__file__).parent / "replay_results.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"Results: {out}")

    wb("close_session", {}, SESSION)
    print("Session closed.")


def main():
    p = argparse.ArgumentParser(description="Batch QA replay via WebBridge")
    p.add_argument("--csv", default=str(CSV_PATH))
    p.add_argument("--start", type=int, default=0)
    p.add_argument("--end", type=int, default=-1)
    p.add_argument("--delay", type=float, default=CFG["delay_between"])
    p.add_argument("--timeout", type=int, default=CFG["response_timeout"])
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    CFG["delay_between"] = args.delay
    CFG["response_timeout"] = args.timeout

    questions = load_questions(args.csv, args.start, args.end)
    if not questions:
        print("No questions found. Check CSV path and user_question column.")
        sys.exit(1)
    print(f"Loaded {len(questions)} questions")
    run(questions, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
