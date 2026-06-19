#!/usr/bin/env python3
"""
提取每个 conversation_id 的首次问答数据
"""

import json
import sys
from collections import defaultdict
from typing import Any


def load_qa_data(file_path: str) -> list[dict[str, Any]]:
    """加载问答对数据"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"加载数据失败: {e}", file=sys.stderr)
        return []


def extract_first_qa_per_conversation(data: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """提取每个 conversation_id 的首次问答"""
    # 按 conversation_id 分组
    grouped = defaultdict(list)
    for qa in data:
        grouped[qa['conversation_id']].append(qa)

    # 提取每个对话的首次问答
    first_qa_list = []
    for conversation_id, qa_list in grouped.items():
        # 按时间排序，取最早的
        qa_list.sort(key=lambda x: x.get('user_created_at', ''))
        first_qa = qa_list[0]
        first_qa_list.append(first_qa)

    # 按时间排序
    first_qa_list.sort(key=lambda x: x.get('user_created_at', ''))

    return first_qa_list


def main():
    # 加载数据
    data = load_qa_data("scripts/live_qa_data_final_v3.json")

    if not data:
        print("没有数据可处理", file=sys.stderr)
        return

    print(f"加载了 {len(data)} 条问答对", file=sys.stderr)

    # 提取首次问答
    first_qa_list = extract_first_qa_per_conversation(data)

    print(f"提取了 {len(first_qa_list)} 个对话的首次问答", file=sys.stderr)

    # 统计
    total_conversations = len(set(qa['conversation_id'] for qa in data))
    print(f"总对话数: {total_conversations}", file=sys.stderr)
    print(f"首次问答数: {len(first_qa_list)}", file=sys.stderr)

    # 保存到文件
    output_file = "scripts/first_qa_per_conversation.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(first_qa_list, f, ensure_ascii=False, indent=2)

    print(f"已保存到: {output_file}", file=sys.stderr)

    # 输出统计信息
    print("\n" + "=" * 60)
    print("首次问答数据统计")
    print("=" * 60)
    print(f"总对话数: {total_conversations}")
    print(f"首次问答数: {len(first_qa_list)}")
    print(f"平均用户问题长度: {sum(qa['user_question_length'] for qa in first_qa_list) / len(first_qa_list):.1f} 字符")
    print(f"平均助手回答长度: {sum(qa['assistant_answer_length'] for qa in first_qa_list) / len(first_qa_list):.1f} 字符")
    print(f"有工具调用的首次问答: {sum(1 for qa in first_qa_list if qa['tool_calls_count'] > 0)}")
    print("=" * 60)

    # 输出前5个示例
    print("\n前5个首次问答示例:")
    for i, qa in enumerate(first_qa_list[:5], 1):
        print(f"\n{i}. {qa['conversation_title']}")
        print(f"   问题: {qa['user_question'][:50]}...")
        print(f"   工具调用: {qa['tool_calls_count']} 次")
        print(f"   时间: {qa['user_created_at']}")


if __name__ == "__main__":
    main()
