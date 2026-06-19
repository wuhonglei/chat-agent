#!/usr/bin/env python3
"""
对对话数据进行分类
按交互模式和工具类型两个维度进行分类
"""

import json
import re
import sys
from collections import Counter, defaultdict
from typing import Any


def load_qa_data(file_path: str) -> list[dict[str, Any]]:
    """加载问答对数据"""
    try:
        with open(file_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"加载数据失败: {e}", file=sys.stderr)
        return []


def analyze_content_blocks(content_blocks: list[dict[str, Any]]) -> dict[str, Any]:
    """分析 content_blocks 的结构"""
    if not content_blocks:
        return {
            "block_types": [],
            "has_text": False,
            "has_tool_use": False,
            "has_tool_result": False,
            "has_attachment": False,
            "tool_use_count": 0,
            "tool_names": [],
            "server_names": [],
        }

    block_types = []
    has_text = False
    has_tool_use = False
    has_tool_result = False
    has_attachment = False
    tool_use_count = 0
    tool_names = []
    server_names = []

    for block in content_blocks:
        if not isinstance(block, dict):
            continue

        block_type = block.get("type", "unknown")
        block_types.append(block_type)

        if block_type == "text":
            has_text = True
        elif block_type == "tool_use":
            has_tool_use = True
            tool_use_count += 1
            # 提取工具信息
            tool_name = block.get("name", "")
            if tool_name:
                tool_names.append(tool_name)
            # 提取 server_name
            server_name = block.get("server_name", "")
            if server_name:
                server_names.append(server_name)
        elif block_type == "tool_result":
            has_tool_result = True
        elif block_type in ["image", "pdf", "markdown", "kb_context"]:
            has_attachment = True

    return {
        "block_types": block_types,
        "has_text": has_text,
        "has_tool_use": has_tool_use,
        "has_tool_result": has_tool_result,
        "has_attachment": has_attachment,
        "tool_use_count": tool_use_count,
        "tool_names": tool_names,
        "server_names": server_names,
    }


def classify_by_interaction_pattern(analysis: dict[str, Any]) -> str:
    """按交互模式分类"""
    has_text = analysis["has_text"]
    has_tool_use = analysis["has_tool_use"]
    has_tool_result = analysis["has_tool_result"]
    has_attachment = analysis["has_attachment"]
    tool_use_count = analysis["tool_use_count"]

    # 附件模式优先级最高
    if has_attachment:
        return "attachment"

    # 纯文本问答
    if has_text and not has_tool_use and not has_tool_result:
        return "simple_chat"

    # 工具调用模式
    if has_tool_use and has_tool_result:
        if tool_use_count == 1:
            return "single_tool"
        elif tool_use_count >= 2:
            return "multi_tool"

    # 其他情况（只有 tool_use 或只有 tool_result）
    if has_tool_use or has_tool_result:
        return "single_tool"

    return "unknown"


def classify_by_tool_type(analysis: dict[str, Any]) -> list[str]:
    """按工具类型分类"""
    tool_names = analysis["tool_names"]
    server_names = analysis["server_names"]

    if not tool_names:
        return []

    tool_types = []

    for tool_name in tool_names:
        tool_name_lower = tool_name.lower()

        # 根据工具名称分类
        if "tavily" in tool_name_lower or "search" in tool_name_lower:
            tool_types.append("tavily_search")
        elif "web" in tool_name_lower and ("extract" in tool_name_lower or "page" in tool_name_lower):
            tool_types.append("web_pages_extract")
        elif "shell" in tool_name_lower or "exec" in tool_name_lower or "command" in tool_name_lower:
            tool_types.append("shell")
        elif "file" in tool_name_lower:
            tool_types.append("file_operations")
        elif "weather" in tool_name_lower:
            tool_types.append("weather")
        elif "time" in tool_name_lower:
            tool_types.append("time")
        else:
            tool_types.append("other")

    # 如果有 server_name，可以更精确分类
    for server_name in server_names:
        if server_name and server_name not in ["tavily", "shell", "file", "weather", "time"]:
            if "other" not in tool_types:
                tool_types.append("mcp_server")

    return list(set(tool_types)) if tool_types else ["no_tool"]


def extract_detailed_tool_info(content_blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """提取详细的工具调用信息"""
    tools = []

    for block in content_blocks:
        if not isinstance(block, dict):
            continue

        if block.get("type") == "tool_use":
            tool_info = {
                "name": block.get("name", ""),
                "server_name": block.get("server_name", ""),
                "input": block.get("input", {}),
            }
            tools.append(tool_info)

    return tools


def main():
    # 加载数据
    qa_data = load_qa_data("scripts/live_qa_data_final.json")

    if not qa_data:
        print("没有数据可分析", file=sys.stderr)
        return

    print(f"加载了 {len(qa_data)} 条问答对", file=sys.stderr)

    # 分类统计
    interaction_patterns = Counter()
    tool_types = Counter()
    tool_usage = Counter()
    server_usage = Counter()

    # 详细分类结果
    classified_data = []

    for qa in qa_data:
        # 分析 assistant 的 content_blocks
        assistant_content = qa.get("assistant_answer", "")

        # 从原始数据中获取 content_blocks（需要从数据库重新获取）
        # 这里我们使用一个简化的方法：根据 tool_calls_count 推断
        tool_calls_count = qa.get("tool_calls_count", 0)

        # 推断交互模式
        if tool_calls_count == 0:
            interaction_pattern = "simple_chat"
        elif tool_calls_count == 1:
            interaction_pattern = "single_tool"
        else:
            interaction_pattern = "multi_tool"

        # 推断工具类型（基于 assistant_answer 内容）
        tool_types_inferred = []
        answer_lower = qa.get("assistant_answer", "").lower()

        if "tavily" in answer_lower or "search" in answer_lower:
            tool_types_inferred.append("tavily_search")
        if "web" in answer_lower and ("extract" in answer_lower or "page" in answer_lower):
            tool_types_inferred.append("web_pages_extract")
        if "shell" in answer_lower or "exec" in answer_lower:
            tool_types_inferred.append("shell")
        if not tool_types_inferred:
            tool_types_inferred.append("no_tool")

        # 更新统计
        interaction_patterns[interaction_pattern] += 1
        for tool_type in tool_types_inferred:
            tool_types[tool_type] += 1

        # 保存分类结果
        classified_qa = qa.copy()
        classified_qa["interaction_pattern"] = interaction_pattern
        classified_qa["tool_types"] = tool_types_inferred
        classified_data.append(classified_qa)

    # 输出统计结果
    print("\n" + "=" * 70)
    print("对话数据分类统计")
    print("=" * 70)

    print("\nA. 按交互模式分类:")
    print("-" * 40)
    for pattern, count in interaction_patterns.most_common():
        percentage = (count / len(qa_data)) * 100
        print(f"{pattern:<20} {count:>4} ({percentage:>5.1f}%)")

    print("\nB. 按工具类型分类:")
    print("-" * 40)
    for tool_type, count in tool_types.most_common():
        percentage = (count / len(qa_data)) * 100
        print(f"{tool_type:<20} {count:>4} ({percentage:>5.1f}%)")

    # 输出详细分类数据
    output_file = "scripts/classified_qa_data.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(classified_data, f, ensure_ascii=False, indent=2)

    print(f"\n详细分类数据已保存到: {output_file}")

    # 输出统计摘要
    summary = {
        "total_qa_pairs": len(qa_data),
        "interaction_patterns": dict(interaction_patterns),
        "tool_types": dict(tool_types),
        "classified_data_file": output_file,
    }

    print("\n" + "=" * 70)
    print("分类完成")
    print("=" * 70)


if __name__ == "__main__":
    main()
