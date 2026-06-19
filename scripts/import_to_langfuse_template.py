#!/usr/bin/env python3
"""
Langfuse 数据导入脚本模板
用于将问答数据导入 Langfuse 进行可观测性分析
"""

import json
import os
import sys
import time
from typing import Any, Optional
from datetime import datetime

import yaml


def load_nacos_config(prod: bool = True) -> dict[str, Any]:
    """从 nacos 配置文件加载配置"""
    config_path = os.path.join(
        os.path.dirname(__file__),
        "..",
        "backend",
        "nacos-data",
        "config",
        "ai-chat-prod@@DEFAULT_GROUP@@" if prod else "ai-chat-dev@@DEFAULT_GROUP@@",
    )

    if not os.path.exists(config_path):
        print(f"❌ 配置文件不存在: {config_path}", file=sys.stderr)
        return {}

    try:
        with open(config_path) as f:
            cfg = yaml.safe_load(f)
        return cfg if isinstance(cfg, dict) else {}
    except Exception as e:
        print(f"❌ 读取配置文件失败: {e}", file=sys.stderr)
        return {}


def load_qa_data(file_path: str) -> list[dict[str, Any]]:
    """加载问答数据"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception as e:
        print(f"❌ 加载数据失败: {e}", file=sys.stderr)
        return []


def create_trace_for_conversation(
    langfuse_client: Any,
    qa_data: dict[str, Any],
    source: str = "historical_data"
) -> Optional[str]:
    """为对话创建 Trace"""
    try:
        trace_id = f"trace_{qa_data['conversation_id']}"

        # 准备元数据
        metadata = {
            "conversation_title": qa_data.get('conversation_title', ''),
            "tool_calls_count": qa_data.get('tool_calls_count', 0),
            "tool_names": qa_data.get('tool_names', []),
            "server_names": qa_data.get('server_names', []),
            "user_question_length": qa_data.get('user_question_length', 0),
            "assistant_answer_length": qa_data.get('assistant_answer_length', 0),
            "response_time_ms": qa_data.get('response_time_ms'),
            "source": source,
        }

        # 创建 Trace
        trace = langfuse_client.trace(
            id=trace_id,
            name="chat_conversation",
            session_id=qa_data['conversation_id'],
            user_id=qa_data.get('user_id', 'unknown'),
            input={
                "question": qa_data.get('user_question', ''),
                "question_length": qa_data.get('user_question_length', 0),
            },
            output={
                "answer": qa_data.get('assistant_answer', '')[:500],
                "answer_length": qa_data.get('assistant_answer_length', 0),
            },
            metadata=metadata,
            tags=["historical", source],
        )

        return trace_id
    except Exception as e:
        print(f"❌ 创建 Trace 失败: {e}", file=sys.stderr)
        return None


def create_latency_span(
    langfuse_client: Any,
    trace_id: str,
    qa_data: dict[str, Any]
) -> bool:
    """创建延迟 Span"""
    try:
        if not qa_data.get('response_time_ms'):
            return True

        # 解析时间戳
        user_time = qa_data.get('user_created_at')
        assistant_time = qa_data.get('assistant_created_at')

        if not user_time or not assistant_time:
            return True

        # 创建 Span
        span = langfuse_client.span(
            trace_id=trace_id,
            name="response_latency",
            start_time=user_time,
            end_time=assistant_time,
            input={
                "question": qa_data.get('user_question', ''),
            },
            output={
                "answer_preview": qa_data.get('assistant_answer', '')[:200],
            },
            metadata={
                "response_time_ms": qa_data.get('response_time_ms'),
                "tool_calls_count": qa_data.get('tool_calls_count', 0),
            },
        )

        return True
    except Exception as e:
        print(f"❌ 创建延迟 Span 失败: {e}", file=sys.stderr)
        return False


def create_tool_generation(
    langfuse_client: Any,
    trace_id: str,
    qa_data: dict[str, Any]
) -> bool:
    """创建工具调用 Generation"""
    try:
        if qa_data.get('tool_calls_count', 0) == 0:
            return True

        # 创建 Generation
        generation = langfuse_client.generation(
            trace_id=trace_id,
            name="tool_execution",
            model="unknown",
            input={
                "tool_names": qa_data.get('tool_names', []),
                "server_names": qa_data.get('server_names', []),
            },
            output={
                "tool_calls_count": qa_data.get('tool_calls_count', 0),
            },
            usage={
                "inputTokens": 0,
                "outputTokens": 0,
                "totalTokens": 0,
            },
            metadata={
                "tool_calls": qa_data.get('tool_calls', []),
            },
        )

        return True
    except Exception as e:
        print(f"❌ 创建工具调用 Generation 失败: {e}", file=sys.stderr)
        return False


def import_batch_to_langfuse(
    langfuse_client: Any,
    qa_data_list: list[dict[str, Any]],
    batch_size: int = 50,
    source: str = "historical_data"
) -> dict[str, int]:
    """批量导入数据到 Langfuse"""
    stats = {
        "total": len(qa_data_list),
        "success": 0,
        "failed": 0,
        "skipped": 0,
    }

    print(f"\n开始导入 {stats['total']} 条数据...")
    print(f"批次大小: {batch_size}")

    for i in range(0, len(qa_data_list), batch_size):
        batch = qa_data_list[i:i + batch_size]
        batch_num = i // batch_size + 1
        total_batches = (len(qa_data_list) + batch_size - 1) // batch_size

        print(f"\n处理批次 {batch_num}/{total_batches} ({len(batch)} 条)")

        batch_success = 0
        batch_failed = 0

        for qa_data in batch:
            # 创建 Trace
            trace_id = create_trace_for_conversation(langfuse_client, qa_data, source)

            if not trace_id:
                batch_failed += 1
                continue

            # 创建延迟 Span
            create_latency_span(langfuse_client, trace_id, qa_data)

            # 创建工具调用 Generation
            create_tool_generation(langfuse_client, trace_id, qa_data)

            batch_success += 1

        stats["success"] += batch_success
        stats["failed"] += batch_failed

        print(f"  ✅ 成功: {batch_success}, ❌ 失败: {batch_failed}")

        # 批次间延迟，避免 API 限流
        if i + batch_size < len(qa_data_list):
            time.sleep(1)

    return stats


def main():
    """主函数"""
    print("=" * 60)
    print("Langfuse 数据导入工具")
    print("=" * 60)

    # 加载配置
    config = load_nacos_config(prod=True)

    if not config:
        print("❌ 无法加载配置", file=sys.stderr)
        sys.exit(1)

    lf_config = config.get("langfuse", {})

    if not lf_config.get("enabled"):
        print("❌ Langfuse 未启用", file=sys.stderr)
        sys.exit(1)

    # 初始化 Langfuse 客户端
    try:
        from langfuse import Langfuse

        langfuse_client = Langfuse(
            public_key=lf_config.get("public_key"),
            secret_key=lf_config.get("secret_key"),
            host=lf_config.get("host"),
        )

        print(f"✅ Langfuse 客户端初始化成功")
        print(f"   Host: {lf_config.get('host')}")
    except Exception as e:
        print(f"❌ Langfuse 客户端初始化失败: {e}", file=sys.stderr)
        sys.exit(1)

    # 加载数据
    print("\n加载数据文件...")

    # 加载首次问答数据
    first_qa_data = load_qa_data("scripts/first_qa_per_conversation.json")
    print(f"  - 首次问答数据: {len(first_qa_data)} 条")

    # 加载完整问答数据
    full_qa_data = load_qa_data("scripts/live_qa_data_final_v3.json")
    print(f"  - 完整问答数据: {len(full_qa_data)} 条")

    # 选择导入数据集
    print("\n请选择要导入的数据集:")
    print("1. 首次问答数据 (441 条)")
    print("2. 完整问答数据 (879 条)")
    print("3. 全部数据 (1320 条)")

    # 默认导入首次问答数据
    choice = "1"
    print(f"\n默认选择: 1. 首次问答数据")

    if choice == "1":
        data_to_import = first_qa_data
        source = "first_qa"
    elif choice == "2":
        data_to_import = full_qa_data
        source = "full_qa"
    else:
        data_to_import = first_qa_data + full_qa_data
        source = "all_qa"

    print(f"\n准备导入 {len(data_to_import)} 条数据")
    print(f"数据源: {source}")

    # 执行导入
    stats = import_batch_to_langfuse(
        langfuse_client,
        data_to_import,
        batch_size=50,
        source=source,
    )

    # 刷新 Langfuse 缓冲区
    print("\n刷新 Langfuse 缓冲区...")
    try:
        langfuse_client.flush()
        print("✅ 缓冲区刷新成功")
    except Exception as e:
        print(f"⚠️  缓冲区刷新失败: {e}")

    # 输出统计
    print("\n" + "=" * 60)
    print("导入完成统计")
    print("=" * 60)
    print(f"总记录数: {stats['total']}")
    print(f"成功导入: {stats['success']}")
    print(f"导入失败: {stats['failed']}")
    print(f"成功率: {stats['success']/stats['total']*100:.1f}%")

    if stats['failed'] > 0:
        print(f"\n⚠️  有 {stats['failed']} 条记录导入失败，请检查日志")

    print("\n✅ 数据导入完成")


if __name__ == "__main__":
    main()
