#!/usr/bin/env python3
"""
按照 conversation_title 对问答数据进行去重
"""

import json
import sys
from typing import Any
from collections import defaultdict


def load_qa_data(file_path: str) -> list[dict[str, Any]]:
    """加载问答数据"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception as e:
        print(f"❌ 加载数据失败: {e}", file=sys.stderr)
        return []


def deduplicate_by_title(data: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """按照 conversation_title 去重"""
    # 按标题分组
    grouped = defaultdict(list)
    for qa in data:
        title = qa.get('conversation_title', '')
        grouped[title].append(qa)

    # 每个标题只保留第一条记录
    deduplicated = []
    for title, qa_list in grouped.items():
        # 按时间排序，取最早的
        qa_list.sort(key=lambda x: x.get('user_created_at', ''))
        deduplicated.append(qa_list[0])

    # 按时间排序
    deduplicated.sort(key=lambda x: x.get('user_created_at', ''))

    return deduplicated


def main():
    # 加载数据
    data = load_qa_data("scripts/first_qa_per_conversation.json")

    if not data:
        print("❌ 没有数据可处理", file=sys.stderr)
        return

    print(f"加载了 {len(data)} 条问答对", file=sys.stderr)

    # 统计去重前的标题分布
    titles_before = defaultdict(int)
    for qa in data:
        title = qa.get('conversation_title', '')
        titles_before[title] += 1

    # 去重
    deduplicated = deduplicate_by_title(data)

    print(f"去重后剩余 {len(deduplicated)} 条问答对", file=sys.stderr)
    print(f"删除了 {len(data) - len(deduplicated)} 条重复记录", file=sys.stderr)

    # 统计去重后的标题分布
    titles_after = defaultdict(int)
    for qa in deduplicated:
        title = qa.get('conversation_title', '')
        titles_after[title] += 1

    # 找出被删除的重复标题
    removed_titles = []
    for title, count in titles_before.items():
        if count > 1:
            removed_titles.append((title, count))

    # 输出统计
    print("\n" + "=" * 60)
    print("去重统计")
    print("=" * 60)
    print(f"去重前: {len(data)} 条")
    print(f"去重后: {len(deduplicated)} 条")
    print(f"删除重复: {len(data) - len(deduplicated)} 条")
    print(f"去重率: {(len(data) - len(deduplicated)) / len(data) * 100:.1f}%")

    if removed_titles:
        print(f"\n重复的标题 ({len(removed_titles)} 个):")
        for i, (title, count) in enumerate(removed_titles[:10], 1):
            print(f"  {i}. {title[:50]}... ({count} 次)")
        if len(removed_titles) > 10:
            print(f"  ... 还有 {len(removed_titles) - 10} 个")

    # 保存去重后的数据
    output_file = "scripts/first_qa_per_conversation_deduplicated.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(deduplicated, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 去重后的数据已保存到: {output_file}")

    # 统计工具调用分布
    tool_counts = {}
    for qa in deduplicated:
        count = qa.get('tool_calls_count', 0)
        tool_counts[count] = tool_counts.get(count, 0) + 1

    print(f"\n工具调用分布:")
    for count, freq in sorted(tool_counts.items()):
        print(f"  {count} 次: {freq} 条 ({freq/len(deduplicated)*100:.1f}%)")


if __name__ == "__main__":
    main()
