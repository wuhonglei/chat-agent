#!/usr/bin/env python3
"""
问答对回放脚本
通过 API 重新发送问答对，测试系统性能并记录到 Langfuse
"""

import argparse
import json
import os
import sys
import time
import requests
from typing import Any, Optional
from datetime import datetime

from nacos_config import load_nacos_config


def load_qa_data(file_path: str) -> list[dict[str, Any]]:
    """加载问答数据"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception as e:
        print(f"❌ 加载数据失败: {e}", file=sys.stderr)
        return []


def get_auth_token(api_base: str, username: str, password: str) -> Optional[str]:
    """获取认证 token"""
    try:
        url = f"{api_base}/api/auth/login"
        payload = {
            "username": username,
            "password": password,
        }

        response = requests.post(url, json=payload, timeout=10)

        if response.status_code == 200:
            data = response.json()
            return data.get("access_token")
        else:
            print(f"❌ 登录失败: {response.status_code} - {response.text}", file=sys.stderr)
            return None
    except Exception as e:
        print(f"❌ 登录异常: {e}", file=sys.stderr)
        return None


def create_conversation(api_base: str, token: str, user_id: str) -> Optional[str]:
    """创建新对话"""
    try:
        url = f"{api_base}/api/conversations"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        payload = {
            "user_id": user_id,
            "title": f"回放测试 - {datetime.now().strftime('%Y%m%d_%H%M%S')}",
        }

        response = requests.post(url, json=payload, headers=headers, timeout=10)

        if response.status_code == 200:
            data = response.json()
            return data.get("id")
        else:
            print(f"❌ 创建对话失败: {response.status_code} - {response.text}", file=sys.stderr)
            return None
    except Exception as e:
        print(f"❌ 创建对话异常: {e}", file=sys.stderr)
        return None


def send_question(
    api_base: str,
    token: str,
    conversation_id: str,
    question: str,
    model: str = "default"
) -> dict[str, Any]:
    """发送问题并获取响应"""
    result: dict[str, Any] = {
        "success": False,
        "question": question,
        "answer": None,
        "response_time_ms": 0,
        "tool_calls_count": 0,
        "tool_names": [],
        "error": None,
    }

    try:
        url = f"{api_base}/api/chat"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        payload = {
            "conversation_id": conversation_id,
            "message": question,
            "model": model,
        }

        start_time = time.time()
        response = requests.post(url, json=payload, headers=headers, timeout=120)
        end_time = time.time()

        result["response_time_ms"] = int((end_time - start_time) * 1000)

        if response.status_code == 200:
            data = response.json()
            result["success"] = True
            result["answer"] = data.get("response", "")

            # 提取工具调用信息
            tool_calls = data.get("tool_calls", [])
            result["tool_calls_count"] = len(tool_calls)
            result["tool_names"] = [tc.get("name", "") for tc in tool_calls]

        else:
            result["error"] = f"HTTP {response.status_code}: {response.text}"

    except requests.exceptions.Timeout:
        result["error"] = "请求超时 (120秒)"
    except Exception as e:
        result["error"] = str(e)

    return result


def replay_qa_pairs(
    api_base: str,
    token: str,
    user_id: str,
    qa_data: list[dict[str, Any]],
    batch_size: int = 10,
    delay_between_questions: float = 2.0,
    model: str = "default"
) -> dict[str, Any]:
    """回放问答对"""
    stats: dict[str, Any] = {
        "total": len(qa_data),
        "success": 0,
        "failed": 0,
        "timeout": 0,
        "total_response_time_ms": 0,
        "avg_response_time_ms": 0.0,
        "tool_calls_total": 0,
        "elapsed_time": 0.0,
        "questions_per_minute": 0.0,
    }

    results = []

    print(f"\n开始回放 {stats['total']} 个问答对...")
    print(f"批次大小: {batch_size}")
    print(f"问题间延迟: {delay_between_questions} 秒")
    print(f"模型: {model}")
    print("=" * 60)

    # 创建对话
    conversation_id = create_conversation(api_base, token, user_id)

    if not conversation_id:
        print("❌ 无法创建对话", file=sys.stderr)
        return stats

    print(f"✅ 创建对话成功: {conversation_id}")

    start_time = time.time()

    for i, qa in enumerate(qa_data):
        question = qa.get("user_question", "")

        if not question:
            continue

        print(f"\n[{i+1}/{len(qa_data)}] 发送问题: {question[:50]}...")

        # 发送问题
        result = send_question(api_base, token, conversation_id, question, model)

        # 更新统计
        if result["success"]:
            stats["success"] += 1
            stats["total_response_time_ms"] += result["response_time_ms"]
            stats["tool_calls_total"] += result["tool_calls_count"]

            print(f"  ✅ 成功 (响应时间: {result['response_time_ms']}ms, 工具调用: {result['tool_calls_count']}次)")
        else:
            stats["failed"] += 1
            print(f"  ❌ 失败: {result['error']}")

        results.append(result)

        # 问题间延迟
        if i < len(qa_data) - 1:
            time.sleep(delay_between_questions)

    elapsed_time = time.time() - start_time

    # 计算平均响应时间
    if stats["success"] > 0:
        stats["avg_response_time_ms"] = stats["total_response_time_ms"] / stats["success"]

    stats["elapsed_time"] = elapsed_time
    stats["questions_per_minute"] = stats["total"] / (elapsed_time / 60) if elapsed_time > 0 else 0.0

    return stats


def save_replay_results(
    results: list[dict[str, Any]],
    stats: dict[str, Any],
    output_file: str
) -> bool:
    """保存回放结果"""
    try:
        output_data = {
            "timestamp": datetime.now().isoformat(),
            "stats": stats,
            "results": results,
        }

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)

        print(f"\n✅ 回放结果已保存到: {output_file}")
        return True
    except Exception as e:
        print(f"❌ 保存结果失败: {e}", file=sys.stderr)
        return False


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="问答对回放工具")
    parser.add_argument(
        "--input",
        required=True,
        help="输入 JSON 文件路径"
    )
    parser.add_argument(
        "--api-base",
        default="http://localhost:8000",
        help="API 基础地址 (默认: http://localhost:8000)"
    )
    parser.add_argument(
        "--username",
        default=None,
        help="登录用户名（也可通过 REPLAY_USERNAME 环境变量设置）"
    )
    parser.add_argument(
        "--password",
        default=None,
        help="登录密码（也可通过 REPLAY_PASSWORD 环境变量设置）"
    )
    parser.add_argument(
        "--user-id",
        default="default_user",
        help="用户 ID (默认: default_user)"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=10,
        help="批次大小 (默认: 10)"
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=2.0,
        help="问题间延迟秒数 (默认: 2.0)"
    )
    parser.add_argument(
        "--model",
        default="default",
        help="使用的模型 (默认: default)"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="最多回放 N 个问题 (0 表示全部)"
    )
    parser.add_argument(
        "--output",
        default="scripts/replay_results.json",
        help="输出文件路径"
    )
    parser.add_argument(
        "--prod",
        action="store_true",
        help="使用生产环境配置"
    )

    args = parser.parse_args()

    username = args.username or os.environ.get("REPLAY_USERNAME")
    password = args.password or os.environ.get("REPLAY_PASSWORD")
    if not username or not password:
        print(
            "❌ 请通过 --username/--password 或 REPLAY_USERNAME/REPLAY_PASSWORD 提供登录凭证",
            file=sys.stderr,
        )
        sys.exit(1)

    print("=" * 60)
    print("问答对回放工具")
    print("=" * 60)
    print(f"输入文件: {args.input}")
    print(f"API 地址: {args.api_base}")
    print(f"用户名: {username}")
    print(f"用户 ID: {args.user_id}")
    print(f"批次大小: {args.batch_size}")
    print(f"问题间延迟: {args.delay} 秒")
    print(f"模型: {args.model}")
    print(f"限制: {args.limit if args.limit > 0 else '无'}")
    print(f"输出文件: {args.output}")

    # 加载配置
    config = load_nacos_config(prod=args.prod)

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

    # 获取认证 token
    print(f"\n获取认证 token...")
    token = get_auth_token(args.api_base, username, password)

    if not token:
        print("❌ 无法获取认证 token", file=sys.stderr)
        sys.exit(1)

    print(f"✅ 认证成功")

    # 执行回放
    stats = replay_qa_pairs(
        api_base=args.api_base,
        token=token,
        user_id=args.user_id,
        qa_data=qa_data,
        batch_size=args.batch_size,
        delay_between_questions=args.delay,
        model=args.model,
    )

    # 保存结果
    save_replay_results([], stats, args.output)

    # 输出统计
    print("\n" + "=" * 60)
    print("回放完成统计")
    print("=" * 60)
    print(f"总问题数: {stats['total']}")
    print(f"成功回放: {stats['success']}")
    print(f"回放失败: {stats['failed']}")
    print(f"成功率: {stats['success']/stats['total']*100:.1f}%")
    print(f"总耗时: {stats['elapsed_time']:.1f} 秒")
    print(f"平均每分钟: {stats['questions_per_minute']:.1f} 个问题")
    print(f"平均响应时间: {stats['avg_response_time_ms']:.0f} ms")
    print(f"工具调用总数: {stats['tool_calls_total']}")

    if stats['failed'] > 0:
        print(f"\n⚠️  有 {stats['failed']} 个问题回放失败，请检查日志")
    else:
        print(f"\n✅ 全部问题回放成功")


if __name__ == "__main__":
    main()
