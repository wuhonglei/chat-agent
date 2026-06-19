#!/usr/bin/env python3
"""
使用 Kimi WebBridge 批量回放问答对
每个问题都在新的对话中进行
"""

import argparse
import json
import os
import sys
import time
from typing import Any, Optional
from datetime import datetime

import requests

from nacos_config import get_frontend_chat_url, load_nacos_config

CHAT_URL = ""


def load_qa_data(file_path: str) -> list[dict[str, Any]]:
    """加载问答数据"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception as e:
        print(f"❌ 加载数据失败: {e}", file=sys.stderr)
        return []


def webbridge_command(action: str, args: dict[str, Any], session: str) -> dict[str, Any]:
    """发送 WebBridge 命令"""
    url = "http://127.0.0.1:10086/command"
    payload = {
        "action": action,
        "args": args,
        "session": session,
    }

    try:
        response = requests.post(url, json=payload, timeout=30)
        return response.json()
    except Exception as e:
        return {"ok": False, "error": {"message": str(e)}}


def navigate_to_new_chat(session: str) -> bool:
    """导航到新的聊天页面"""
    result = webbridge_command("navigate", {
        "url": CHAT_URL,
        "newTab": True,
        "group_title": f"回放测试 - {session}"
    }, session)

    return result.get("ok", False)


def send_question(session: str, question: str) -> bool:
    """发送问题"""
    # 等待页面加载
    time.sleep(1)

    # 设置输入框值
    code = f"""
    (() => {{
        const textarea = document.querySelector("textarea");
        if (textarea) {{
            textarea.focus();
            const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
                window.HTMLTextAreaElement.prototype, "value"
            ).set;
            nativeInputValueSetter.call(textarea, {json.dumps(question)});
            textarea.dispatchEvent(new Event("input", {{ bubbles: true }}));
            return {{ success: true, value: textarea.value }};
        }}
        return {{ success: false }};
    }})()
    """

    result = webbridge_command("evaluate", {"code": code}, session)

    if not result.get("ok", False):
        return False

    # 触发 Enter 键
    enter_code = """
    (() => {
        const textarea = document.querySelector("textarea");
        if (textarea) {
            textarea.dispatchEvent(new KeyboardEvent("keydown", {
                key: "Enter",
                code: "Enter",
                keyCode: 13,
                which: 13,
                bubbles: true,
                cancelable: true
            }));
            return "keydown dispatched";
        }
        return "textarea not found";
    })()
    """

    result = webbridge_command("evaluate", {"code": enter_code}, session)
    return result.get("ok", False)


def wait_for_response(session: str, timeout: int = 30) -> dict[str, Any]:
    """等待 AI 响应"""
    start_time = time.time()

    while time.time() - start_time < timeout:
        time.sleep(2)

        # 获取页面快照
        result = webbridge_command("snapshot", {}, session)

        if not result.get("ok", False):
            continue

        data = result.get("data", {})
        tree = data.get("tree", [])

        # 检查是否有 AI 响应
        tree_str = json.dumps(tree, ensure_ascii=False)

        # 检查是否有工具调用或长文本响应
        if "工具调用成功" in tree_str or len(tree_str) > 5000:
            elapsed = time.time() - start_time
            return {
                "success": True,
                "elapsed_seconds": elapsed,
                "has_tool_calls": "工具调用成功" in tree_str,
            }

    return {"success": False, "error": "timeout"}


def close_session(session: str) -> bool:
    """关闭会话"""
    result = webbridge_command("close_session", {}, session)
    return result.get("ok", False)


def replay_single_question(
    question: str,
    question_index: int,
    total: int,
) -> dict[str, Any]:
    """回放单个问题（在新对话中）"""
    session = f"replay-{question_index}"

    print(f"\n[{question_index}/{total}] 发送问题: {question[:50]}...")

    start_time = time.time()

    # 1. 打开新的聊天页面
    if not navigate_to_new_chat(session):
        return {
            "success": False,
            "error": "无法打开聊天页面",
            "question": question,
        }

    print(f"  ✅ 已打开新对话")

    # 2. 发送问题
    if not send_question(session, question):
        close_session(session)
        return {
            "success": False,
            "error": "发送问题失败",
            "question": question,
        }

    # 3. 等待响应
    result = wait_for_response(session, timeout=30)

    elapsed = time.time() - start_time

    # 4. 关闭会话
    close_session(session)
    print(f"  ✅ 已关闭会话")

    if result.get("success"):
        print(f"  ✅ 成功 (耗时: {elapsed:.1f}秒, 工具调用: {'是' if result.get('has_tool_calls') else '否'})")
        return {
            "success": True,
            "question": question,
            "elapsed_seconds": elapsed,
            "has_tool_calls": result.get("has_tool_calls", False),
        }
    else:
        print(f"  ❌ 失败: {result.get('error', '未知错误')}")
        return {
            "success": False,
            "error": result.get("error", "未知错误"),
            "question": question,
        }


def replay_all_questions(
    qa_data: list[dict[str, Any]],
    delay_between_questions: float = 3.0,
) -> dict[str, Any]:
    """回放所有问题（每个问题在新对话中）"""
    stats: dict[str, Any] = {
        "total": len(qa_data),
        "success": 0,
        "failed": 0,
        "tool_calls_count": 0,
        "total_elapsed": 0.0,
        "avg_elapsed": 0.0,
        "questions_per_minute": 0.0,
    }

    results = []

    print(f"\n开始回放 {stats['total']} 个问题...")
    print(f"问题间延迟: {delay_between_questions} 秒")
    print(f"每个问题都在新对话中进行")
    print("=" * 60)

    start_time = time.time()

    # 回放每个问题
    for i, qa in enumerate(qa_data):
        question = qa.get("user_question", "")

        if not question:
            continue

        result = replay_single_question(
            question=question,
            question_index=i + 1,
            total=len(qa_data),
        )

        if result.get("success"):
            stats["success"] += 1
            if result.get("has_tool_calls"):
                stats["tool_calls_count"] += 1
        else:
            stats["failed"] += 1

        results.append(result)

        # 问题间延迟
        if i < len(qa_data) - 1:
            time.sleep(delay_between_questions)

    elapsed = time.time() - start_time
    stats["total_elapsed"] = elapsed
    stats["avg_elapsed"] = stats["success"] / elapsed if elapsed > 0 else 0.0
    stats["questions_per_minute"] = stats["total"] / (elapsed / 60) if elapsed > 0 else 0.0

    return stats


def save_results(
    results: list[dict[str, Any]],
    stats: dict[str, Any],
    output_file: str,
) -> bool:
    """保存结果"""
    try:
        output_data = {
            "timestamp": datetime.now().isoformat(),
            "stats": stats,
            "results": results,
        }

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)

        print(f"\n✅ 结果已保存到: {output_file}")
        return True
    except Exception as e:
        print(f"❌ 保存结果失败: {e}", file=sys.stderr)
        return False


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="使用 Kimi WebBridge 批量回放问答对")
    parser.add_argument(
        "--input",
        required=True,
        help="输入 JSON 文件路径"
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=3.0,
        help="问题间延迟秒数 (默认: 3.0)"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="最多回放 N 个问题 (0 表示全部)"
    )
    parser.add_argument(
        "--output",
        default="scripts/replay_new_conversation_results.json",
        help="输出文件路径"
    )
    parser.add_argument(
        "--prod",
        action="store_true",
        help="使用生产环境配置"
    )
    parser.add_argument(
        "--chat-url",
        default=None,
        help="聊天页 URL（默认从 nacos 配置 cors.allow_origins 推断）"
    )

    args = parser.parse_args()

    global CHAT_URL
    config = load_nacos_config(prod=args.prod)
    CHAT_URL = args.chat_url or get_frontend_chat_url(config)
    if not CHAT_URL:
        print("❌ 无法确定聊天页 URL，请通过 --chat-url 指定", file=sys.stderr)
        sys.exit(1)

    print("=" * 60)
    print("使用 Kimi WebBridge 批量回放问答对")
    print("每个问题都在新对话中进行")
    print("=" * 60)
    print(f"聊天页 URL: {CHAT_URL}")
    print(f"输入文件: {args.input}")
    print(f"问题间延迟: {args.delay} 秒")
    print(f"限制: {args.limit if args.limit > 0 else '无'}")
    print(f"输出文件: {args.output}")

    # 加载数据
    print(f"\n加载数据文件...")
    qa_data = load_qa_data(args.input)

    if not qa_data:
        print("❌ 没有数据可回放", file=sys.stderr)
        sys.exit(1)

    print(f"  - 总记录数: {len(qa_data)}")

    # 应用限制
    if args.limit > 0:
        qa_data = qa_data[:args.limit]
        print(f"  - 限制回放: {len(qa_data)} 条")

    # 执行回放
    stats = replay_all_questions(
        qa_data=qa_data,
        delay_between_questions=args.delay,
    )

    # 保存结果
    save_results([], stats, args.output)

    # 输出统计
    print("\n" + "=" * 60)
    print("回放完成统计")
    print("=" * 60)
    print(f"总问题数: {stats['total']}")
    print(f"成功回放: {stats['success']}")
    print(f"回放失败: {stats['failed']}")
    print(f"成功率: {stats['success']/stats['total']*100:.1f}%")
    print(f"总耗时: {stats['total_elapsed']:.1f} 秒")
    print(f"平均每分钟: {stats['questions_per_minute']:.1f} 个问题")
    print(f"工具调用次数: {stats['tool_calls_count']}")

    if stats['failed'] > 0:
        print(f"\n⚠️  有 {stats['failed']} 个问题回放失败，请检查日志")
    else:
        print(f"\n✅ 全部问题回放成功")


if __name__ == "__main__":
    main()
