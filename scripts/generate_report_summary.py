#!/usr/bin/env python3
"""
生成简洁的分类报告文件
"""

import json
from collections import Counter, defaultdict


def load_classified_data(file_path: str):
    """加载分类数据"""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def main():
    # 加载分类数据
    data = load_classified_data("scripts/classified_qa_data_final.json")

    # 统计
    interaction_patterns = Counter()
    tool_types = Counter()
    tool_usage = Counter()
    server_usage = Counter()

    for item in data:
        interaction_patterns[item["interaction_pattern"]] += 1
        for tool_type in item["tool_types"]:
            tool_types[tool_type] += 1
        for tool_name in item["tool_names"]:
            tool_usage[tool_name] += 1
        for server_name in item["server_names"]:
            server_usage[server_name] += 1

    # 生成报告
    report = {
        "summary": {
            "total_qa_pairs": len(data),
            "interaction_patterns": dict(interaction_patterns),
            "tool_types": dict(tool_types),
        },
        "detailed_stats": {
            "tool_usage": dict(tool_usage.most_common()),
            "server_usage": dict(server_usage.most_common()),
        },
        "classification_rules": {
            "interaction_patterns": {
                "simple_chat": "纯文本问答（无工具调用）",
                "single_tool": "单轮工具调用（恰好 1 组 tool_use+tool_result）",
                "multi_tool": "多轮工具调用（2+ 组 tool_use+tool_result，Agent 循环）",
                "attachment": "含附件（image/pdf/markdown/kb_context）",
            },
            "tool_types": {
                "tavily_search": "网页搜索（tavily_web_search）",
                "web_pages_extract": "网页抓取（tavily_web_pages_extract）",
                "shell": "Shell 执行（shell_shell）",
                "file_operations": "文件操作（file_*）",
                "mcp_server": "其他 MCP Server（context7, zread, code 等）",
                "no_tool": "无工具调用",
            },
        },
        "data_files": {
            "classified_data": "scripts/classified_qa_data_final.json",
            "original_data": "scripts/live_qa_data_final.json",
            "simple_conversations": "scripts/simple_conversations.json",
        },
    }

    # 保存报告
    report_file = "scripts/classification_report.json"
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"分类报告已保存到: {report_file}")

    # 打印摘要
    print("\n" + "=" * 60)
    print("对话数据分类摘要")
    print("=" * 60)
    print(f"总问答对数量: {len(data)}")
    print("\n交互模式分布:")
    for pattern, count in interaction_patterns.most_common():
        percentage = (count / len(data)) * 100
        print(f"  {pattern:<20} {count:>4} ({percentage:>5.1f}%)")

    print("\n工具类型分布:")
    for tool_type, count in tool_types.most_common():
        percentage = (count / len(data)) * 100
        print(f"  {tool_type:<20} {count:>4} ({percentage:>5.1f}%)")


if __name__ == "__main__":
    main()
