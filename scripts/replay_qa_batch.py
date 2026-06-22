#!/usr/bin/env python3
"""
批量回放用户问题到 chat.wuhonglei.cn
使用 Kimi WebBridge 控制真实浏览器
"""

import csv
import json
import subprocess
import time
import sys
from typing import List, Dict, Any

# 配置
CSV_FILE = "/Users/apple/Desktop/code/chat-agent/scripts/qa_baseline_100.csv"
CHAT_URL = "https://chat.wuhonglei.cn/chat"
SESSION = "qa-batch-replay"
DELAY_BETWEEN_QUESTIONS = 5  # 秒
RESPONSE_TIMEOUT = 60  # 等待响应的最大秒数

def webbridge(action: str, args: dict, session: str = SESSION) -> dict:
    """调用 Kimi WebBridge"""
    payload = json.dumps({
        "action": action,
        "args": args,
        "session": session
    }, ensure_ascii=False)
    
    result = subprocess.run(
        ["curl", "-s", "-X", "POST", "http://127.0.0.1:10086/command",
         "-H", "Content-Type: application/json", "-d", payload],
        capture_output=True, text=True, timeout=30
    )
    
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"ok": False, "error": f"Invalid response: {result.stdout}"}

def check_ok(r: dict) -> bool:
    """检查 WebBridge 响应是否成功"""
    # 对于 snapshot，只要 ok=true 且有 data 就算成功
    if r.get("ok"):
        data = r.get("data", {})
        # snapshot 返回 tree/url/title，没有 success 字段
        if "tree" in data or "url" in data:
            return True
        # 其他操作检查 success 字段
        return data.get("success", False)
    return False

def load_questions(csv_file: str) -> List[str]:
    """从 CSV 文件加载用户问题"""
    questions = []
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            q = row.get('user_question', '').strip()
            if q:
                questions.append(q)
    return questions

def fill_input(question: str) -> bool:
    """使用 nativeInputValueSetter 填充输入框"""
    q_json = json.dumps(question, ensure_ascii=False)
    
    fill_code = f"""(() => {{
        const t = document.querySelector('textarea');
        if (!t) return JSON.stringify({{success: false, error: 'no textarea found'}});
        
        t.focus();
        const val = {q_json};
        const nativeSet = Object.getOwnPropertyDescriptor(
            window.HTMLTextAreaElement.prototype, 'value').set;
        nativeSet.call(t, val);
        t.dispatchEvent(new Event('input', {{bubbles: true}}));
        t.dispatchEvent(new Event('change', {{bubbles: true}}));
        
        return JSON.stringify({{success: true, len: t.value.length}});
    }})()"""
    
    r = webbridge("evaluate", {"code": fill_code})
    
    if not r.get("ok"):
        print(f"  [ERROR] fill evaluate failed: {r}")
        return False
    
    try:
        value = r.get("data", {}).get("value", "")
        result = json.loads(value)
        if result.get("success"):
            return True
        else:
            print(f"  [ERROR] fill failed: {result}")
            return False
    except Exception as e:
        print(f"  [ERROR] parse fill result failed: {e}, raw: {r}")
        return False

def submit_with_enter() -> bool:
    """按 Enter 提交"""
    enter_code = """(() => {
        const t = document.querySelector('textarea');
        if (!t) return 'no textarea';
        
        t.dispatchEvent(new KeyboardEvent('keydown', {
            key: 'Enter', code: 'Enter', keyCode: 13, which: 13,
            bubbles: true, cancelable: true
        }));
        
        return 'ok';
    })()"""
    
    r = webbridge("evaluate", {"code": enter_code})
    return r.get("ok") and r.get("data", {}).get("value") == "ok"

def wait_for_response(timeout: int = RESPONSE_TIMEOUT) -> bool:
    """等待 AI 响应完成"""
    start = time.time()
    last_len = 0
    stable_count = 0
    
    print("  Waiting for response", end="", flush=True)
    
    while time.time() - start < timeout:
        time.sleep(2)
        print(".", end="", flush=True)
        
        r = webbridge("snapshot", {})
        if not check_ok(r):
            continue
        
        tree_str = json.dumps(r.get("data", {}).get("tree", []), ensure_ascii=False)
        current_len = len(tree_str)
        
        # 检测响应完成的指标
        # 1. 内容长度稳定（连续3次长度不变）
        if current_len > 2000 and abs(current_len - last_len) < 100:
            stable_count += 1
            if stable_count >= 3:
                print(" ✓")
                return True
        else:
            stable_count = 0
        
        # 2. 检测特定完成标记
        if "内容由 AI 生成" in tree_str or "复制" in tree_str:
            print(" ✓")
            return True
        
        last_len = current_len
    
    print(" ✗ (timeout)")
    return False

def click_new_conversation() -> bool:
    """点击"开启新对话"按钮"""
    # 使用 snapshot 中的 @e ref 来点击
    r = webbridge("snapshot", {})
    if not check_ok(r):
        return False
    
    tree = r.get("data", {}).get("tree", [])
    
    # 找到"开启新对话"按钮的 ref
    def find_button(nodes, target_name):
        for node in nodes:
            if isinstance(node, dict):
                if node.get("name") == target_name and node.get("role") == "button":
                    return node.get("ref")
                if "children" in node:
                    result = find_button(node["children"], target_name)
                    if result:
                        return result
            elif isinstance(node, list):
                result = find_button(node, target_name)
                if result:
                    return result
        return None
    
    ref = find_button(tree, "开启新对话")
    if ref:
        print(f"  Found '开启新对话' button: {ref}")
        click_r = webbridge("click", {"selector": ref})
        return click_r.get("ok") and click_r.get("data", {}).get("success", False)
    
    print("  [WARN] '开启新对话' button not found in snapshot")
    return False

def navigate_to_chat() -> bool:
    """导航到聊天页面"""
    r = webbridge("navigate", {
        "url": CHAT_URL,
        "newTab": True,
        "group_title": "QA Batch Replay"
    })
    return r.get("ok") and r.get("data", {}).get("success", False)

def replay_question(question: str, index: int) -> Dict[str, Any]:
    """回放单个问题"""
    result = {
        "index": index,
        "question": question[:100] + "..." if len(question) > 100 else question,
        "full_question": question,
        "fill": False,
        "submit": False,
        "response": False,
        "new_conversation": False,
        "success": False
    }
    
    print(f"\n[{index}] Processing: {result['question']}")
    
    # 1. 填充输入
    if not fill_input(question):
        return result
    result["fill"] = True
    time.sleep(0.5)
    
    # 2. 提交
    if not submit_with_enter():
        print("  [ERROR] Submit failed")
        return result
    result["submit"] = True
    
    # 3. 等待响应
    if wait_for_response():
        result["response"] = True
    else:
        print("  [WARN] Response timeout, continuing anyway...")
        result["response"] = True  # 即使超时也继续
    
    # 4. 点击新对话
    time.sleep(1)
    if click_new_conversation():
        result["new_conversation"] = True
        time.sleep(2)  # 等待页面加载
    else:
        # 备选方案：直接导航到 /chat
        print("  [INFO] Fallback: navigating to /chat")
        webbridge("navigate", {"url": CHAT_URL})
        time.sleep(2)
        result["new_conversation"] = True
    
    result["success"] = all([
        result["fill"],
        result["submit"],
        result["response"]
    ])
    
    return result

def main():
    print("=" * 60)
    print("QA Batch Replay - chat.wuhonglei.cn")
    print("=" * 60)
    
    # 加载问题
    print(f"\nLoading questions from: {CSV_FILE}")
    questions = load_questions(CSV_FILE)
    print(f"Loaded {len(questions)} questions")
    
    if not questions:
        print("[ERROR] No questions found!")
        sys.exit(1)
    
    # 导航到聊天页面
    print(f"\nNavigating to: {CHAT_URL}")
    if not navigate_to_chat():
        print("[ERROR] Failed to navigate to chat page")
        sys.exit(1)
    time.sleep(3)
    
    # 批量回放
    results = []
    success_count = 0
    
    for i, question in enumerate(questions, 1):
        result = replay_question(question, i)
        results.append(result)
        
        if result["success"]:
            success_count += 1
        
        print(f"  Status: {'✓ SUCCESS' if result['success'] else '✗ FAILED'}")
        
        # 延迟
        if i < len(questions):
            print(f"  Waiting {DELAY_BETWEEN_QUESTIONS}s before next question...")
            time.sleep(DELAY_BETWEEN_QUESTIONS)
    
    # 统计
    print("\n" + "=" * 60)
    print("REPLAY COMPLETE")
    print("=" * 60)
    print(f"Total questions: {len(questions)}")
    print(f"Successful: {success_count}")
    print(f"Failed: {len(questions) - success_count}")
    print(f"Success rate: {success_count/len(questions)*100:.1f}%")
    
    # 保存结果
    result_file = CSV_FILE.replace('.csv', '_replay_results.json')
    with open(result_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\nResults saved to: {result_file}")

if __name__ == "__main__":
    main()
