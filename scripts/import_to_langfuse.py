#!/usr/bin/env python3
"""
Langfuse 数据导入脚本
支持批量导入、错误处理、进度显示
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from typing import Any, Optional

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


def create_quality_score(
    langfuse_client: Any,
    trace_id: str,
    qa_data: dict[str, Any]
) -> bool:
    """创建质量评分"""
    try:
        # 根据响应时间计算质量分数
        response_time = qa_data.get('response_time_ms')
        if response_time is None:
            return True

        # 响应时间评分：< 1秒 = 1.0，1-5秒 = 0.8，5-10秒 = 0.6，> 10秒 = 0.4
        if response_time < 1000:
            score_value = 1.0
            comment = "快速响应 (< 1秒)"
        elif response_time < 5000:
            score_value = 0.8
            comment = "正常响应 (1-5秒)"
        elif response_time < 10000:
            score_value = 0.6
            comment = "较慢响应 (5-10秒)"
        else:
            score_value = 0.4
            comment = "慢响应 (> 10秒)"

        # 创建 Score
        score = langfuse_client.score(
            trace_id=trace_id,
            name="response_time_quality",
            value=score_value,
            comment=comment,
        )

        return True
    except Exception as e:
        print(f"❌ 创建质量评分失败: {e}", file=sys.stderr)
        return False


def import_single_record(
    langfuse_client: Any,
    qa_data: dict[str, Any],
    source: str = "historical_data"
) -> dict[str, Any]:
    """导入单条记录"""
    result = {
        "success": False,
        "trace_id": None,
        "errors": [],
    }

    # 创建 Trace
    trace_id = create_trace_for_conversation(langfuse_client, qa_data, source)
    if not trace_id:
        result["errors"].append("创建 Trace 失败")
        return result

    result["trace_id"] = trace_id

    # 创建延迟 Span
    if not create_latency_span(langfuse_client, trace_id, qa_data):
        result["errors"].append("创建延迟 Span 失败")

    # 创建工具调用 Generation
    if not create_tool_generation(langfuse_client, trace_id, qa_data):
        result["errors"].append("创建工具调用 Generation 失败")

    # 创建质量评分
    if not create_quality_score(langfuse_client, trace_id, qa_data):
        result["errors"].append("创建质量评分失败")

    result["success"] = len(result["errors"]) == 0
    return result


def import_batch_with_retry(
    langfuse_client: Any,
    qa_data_list: list[dict[str, Any]],
    batch_size: int = 50,
    max_retries: int = 3,
    retry_delay: float = 2.0,
    source: str = "historical_data"
) -> dict[str, Any]:
    """批量导入数据，支持重试机制"""
    stats = {
        "total": len(qa_data_list),
        "success": 0,
        "failed": 0,
        "retried": 0,
        "errors": [],
    }

    total_batches = (len(qa_data_list) + batch_size - 1) // batch_size

    print(f"\n开始导入 {stats['total']} 条数据...")
    print(f"批次大小: {batch_size}, 总批次数: {total_batches}")
    print(f"重试次数: {max_retries}, 重试延迟: {retry_delay} 秒")
    print("=" * 60)

    start_time = time.time()

    for batch_idx in range(total_batches):
        batch_start = batch_idx * batch_size
        batch_end = min(batch_start + batch_size, len(qa_data_list))
        batch = qa_data_list[batch_start:batch_end]

        print(f"\n批次 {batch_idx + 1}/{total_batches} ({len(batch)} 条)")

        batch_success = 0
        batch_failed = 0

        for i, qa_data in enumerate(batch):
            record_idx = batch_start + i + 1

            # 重试机制
            for attempt in range(max_retries + 1):
                try:
                    result = import_single_record(langfuse_client, qa_data, source)

                    if result["success"]:
                        batch_success += 1
                        if attempt > 0:
                            stats["retried"] += 1
                        break
                    else:
                        if attempt < max_retries:
                            print(f"  ⚠️  记录 {record_idx} 失败，重试 {attempt + 1}/{max_retries}...")
                            time.sleep(retry_delay * (attempt + 1))  # 指数退避
                        else:
                            batch_failed += 1
                            stats["errors"].append({
                                "record_idx": record_idx,
                                "conversation_id": qa_data.get("conversation_id"),
                                "errors": result["errors"],
                            })
                except Exception as e:
                    if attempt < max_retries:
                        print(f"  ⚠️  记录 {record_idx} 异常，重试 {attempt + 1}/{max_retries}...")
                        time.sleep(retry_delay * (attempt + 1))
                    else:
                        batch_failed += 1
                        stats["errors"].append({
                            "record_idx": record_idx,
                            "conversation_id": qa_data.get("conversation_id"),
                            "errors": [str(e)],
                        })

        stats["success"] += batch_success
        stats["failed"] += batch_failed

        print(f"  ✅ 成功: {batch_success}, ❌ 失败: {batch_failed}")

        # 批次间延迟，避免 API 限流
        if batch_idx < total_batches - 1:
            time.sleep(1)

    elapsed_time = time.time() - start_time
    stats["elapsed_time"] = elapsed_time
    stats["records_per_second"] = stats["total"] / elapsed_time if elapsed_time > 0 else 0

    return stats


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="Langfuse 数据导入工具")
    parser.add_argument(
        "--input",
        required=True,
        help="输入 JSON 文件路径"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=50,
        help="批次大小 (默认: 50)"
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=3,
        help="最大重试次数 (默认: 3)"
    )
    parser.add_argument(
        "--source",
        default="historical_data",
        help="数据源标识 (默认: historical_data)"
    )
    parser.add_argument(
        "--prod",
        action="store_true",
        help="使用生产环境配置"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="试运行，不实际导入"
    )
    parser.add_argument(
        "--offset",
        type=int,
        default=0,
        help="跳过前 N 条记录 (用于断点续传)"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="最多导入 N 条记录 (0 表示全部)"
    )

    args = parser.parse_args()

    print("=" * 60)
    print("Langfuse 数据导入工具")
    print("=" * 60)
    print(f"输入文件: {args.input}")
    print(f"批次大小: {args.batch_size}")
    print(f"最大重试: {args.max_retries}")
    print(f"数据源: {args.source}")
    print(f"环境: {'生产' if args.prod else '开发'}")
    print(f"试运行: {'是' if args.dry_run else '否'}")
    print(f"偏移量: {args.offset}")
    print(f"限制: {args.limit if args.limit > 0 else '无'}")

    # 加载配置
    config = load_nacos_config(prod=args.prod)

    if not config:
        print("❌ 无法加载配置", file=sys.stderr)
        sys.exit(1)

    lf_config = config.get("langfuse", {})

    if not lf_config.get("enabled"):
        print("❌ Langfuse 未启用", file=sys.stderr)
        sys.exit(1)

    # 初始化 Langfuse 客户端
    if not args.dry_run:
        try:
            from langfuse import Langfuse

            langfuse_client = Langfuse(
                public_key=lf_config.get("public_key"),
                secret_key=lf_config.get("secret_key"),
                host=lf_config.get("host"),
            )

            print(f"\n✅ Langfuse 客户端初始化成功")
            print(f"   Host: {lf_config.get('host')}")
        except Exception as e:
            print(f"❌ Langfuse 客户端初始化失败: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        langfuse_client = None
        print(f"\n⚠️  试运行模式，不实际导入")

    # 加载数据
    print(f"\n加载数据文件...")
    qa_data_list = load_qa_data(args.input)

    if not qa_data_list:
        print("❌ 没有数据可导入", file=sys.stderr)
        sys.exit(1)

    print(f"  - 总记录数: {len(qa_data_list)}")

    # 应用偏移量和限制
    if args.offset > 0:
        qa_data_list = qa_data_list[args.offset:]
        print(f"  - 跳过前 {args.offset} 条，剩余: {len(qa_data_list)}")

    if args.limit > 0:
        qa_data_list = qa_data_list[:args.limit]
        print(f"  - 限制导入: {len(qa_data_list)} 条")

    # 试运行模式
    if args.dry_run:
        print(f"\n试运行模式，将导入 {len(qa_data_list)} 条记录")
        print("✅ 试运行完成")
        return

    # 执行导入
    stats = import_batch_with_retry(
        langfuse_client=langfuse_client,
        qa_data_list=qa_data_list,
        batch_size=args.batch_size,
        max_retries=args.max_retries,
        source=args.source,
    )

    # 刷新 Langfuse 缓冲区
    print("\n刷新 Langfuse 缓冲区...")
    try:
        if langfuse_client:
            langfuse_client.flush()
            print("✅ 缓冲区刷新成功")
    except Exception as e:
        print(f"⚠️  缓冲区刷新失败: {e}")

    # 记录导入日志
    try:
        sys.path.insert(0, os.path.dirname(__file__))
        from import_log import add_import_record

        add_import_record(
            data_source=args.source,
            total_records=stats["total"],
            success_count=stats["success"],
            failed_count=stats["failed"],
            duration_seconds=stats["elapsed_time"],
            notes=f"批次大小: {args.batch_size}, 重试次数: {args.max_retries}",
        )
        print("✅ 导入日志已记录")
    except Exception as e:
        print(f"⚠️  记录导入日志失败: {e}")

    # 输出统计
    print("\n" + "=" * 60)
    print("导入完成统计")
    print("=" * 60)
    print(f"总记录数: {stats['total']}")
    print(f"成功导入: {stats['success']}")
    print(f"导入失败: {stats['failed']}")
    print(f"重试次数: {stats['retried']}")
    print(f"成功率: {stats['success']/stats['total']*100:.1f}%")
    print(f"总耗时: {stats['elapsed_time']:.1f} 秒")
    print(f"平均速度: {stats['records_per_second']:.1f} 条/秒")

    if stats['errors']:
        print(f"\n错误详情 (前 5 条):")
        for i, error in enumerate(stats['errors'][:5]):
            print(f"  {i+1}. 记录 {error['record_idx']}: {error['errors']}")

    if stats['failed'] > 0:
        print(f"\n⚠️  有 {stats['failed']} 条记录导入失败，请检查日志")
    else:
        print(f"\n✅ 全部数据导入成功")


if __name__ == "__main__":
    main()
