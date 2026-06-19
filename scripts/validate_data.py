#!/usr/bin/env python3
"""
验证问答数据文件的完整性和质量
"""

import json
import sys
from typing import Any, Optional
from collections import Counter


def load_json_file(file_path: str) -> list[dict[str, Any]]:
    """加载 JSON 文件"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception as e:
        print(f"❌ 加载文件失败 {file_path}: {e}", file=sys.stderr)
        return []


def validate_qa_data(data: list[dict[str, Any]], file_name: str) -> dict[str, Any]:
    """验证问答数据质量"""
    print(f"\n验证文件: {file_name}")
    print("=" * 60)

    if not data:
        print("❌ 数据为空")
        return {"valid": False, "errors": ["数据为空"]}

    errors = []
    warnings = []

    # 检查必需字段
    required_fields = [
        "conversation_id",
        "user_message_id",
        "assistant_message_id",
        "user_question",
        "assistant_answer",
        "tool_calls_count",
    ]

    missing_fields = []
    for field in required_fields:
        if field not in data[0]:
            missing_fields.append(field)

    if missing_fields:
        errors.append(f"缺少必需字段: {missing_fields}")
        print(f"❌ 缺少必需字段: {missing_fields}")
    else:
        print("✅ 必需字段完整")

    # 检查数据完整性
    total_records = len(data)
    valid_records = 0
    invalid_records = []

    for i, record in enumerate(data):
        record_errors = []

        # 检查关键字段是否为空
        if not record.get("conversation_id"):
            record_errors.append("conversation_id 为空")
        if not record.get("user_message_id"):
            record_errors.append("user_message_id 为空")
        if not record.get("assistant_message_id"):
            record_errors.append("assistant_message_id 为空")
        if not record.get("user_question"):
            record_errors.append("user_question 为空")

        if record_errors:
            invalid_records.append((i, record_errors))
        else:
            valid_records += 1

    print(f"\n数据完整性检查:")
    print(f"  - 总记录数: {total_records}")
    print(f"  - 有效记录: {valid_records}")
    print(f"  - 无效记录: {len(invalid_records)}")

    if invalid_records:
        warnings.append(f"有 {len(invalid_records)} 条无效记录")
        print(f"  ⚠️  前 5 条无效记录:")
        for i, (idx, errs) in enumerate(invalid_records[:5]):
            print(f"    {idx}: {errs}")

    # 检查数据类型
    type_errors = []
    for i, record in enumerate(data[:10]):  # 只检查前 10 条
        if not isinstance(record.get("tool_calls_count", 0), int):
            type_errors.append(f"记录 {i}: tool_calls_count 不是整数")
        if record.get("response_time_ms") is not None and not isinstance(record.get("response_time_ms"), int):
            type_errors.append(f"记录 {i}: response_time_ms 类型错误")

    if type_errors:
        warnings.extend(type_errors)
        print(f"\n⚠️  数据类型问题:")
        for err in type_errors[:5]:
            print(f"  - {err}")
    else:
        print("✅ 数据类型检查通过")

    # 统计信息
    print(f"\n数据统计:")
    print(f"  - 唯一 conversation_id: {len(set(r['conversation_id'] for r in data))}")
    print(f"  - 唯一 user_message_id: {len(set(r['user_message_id'] for r in data))}")
    print(f"  - 唯一 assistant_message_id: {len(set(r['assistant_message_id'] for r in data))}")

    # 工具调用统计
    tool_counts = Counter(r.get("tool_calls_count", 0) for r in data)
    print(f"  - 工具调用分布:")
    for count, freq in sorted(tool_counts.items()):
        print(f"    {count} 次: {freq} 条 ({freq/total_records*100:.1f}%)")

    # 时间范围
    timestamps = [r.get("user_created_at") for r in data if r.get("user_created_at")]
    if timestamps:
        timestamps.sort()
        print(f"  - 时间范围: {timestamps[0][:10]} 至 {timestamps[-1][:10]}")

    return {
        "valid": len(errors) == 0,
        "total_records": total_records,
        "valid_records": valid_records,
        "invalid_records": len(invalid_records),
        "errors": errors,
        "warnings": warnings,
    }


def main():
    print("=" * 60)
    print("问答数据质量验证")
    print("=" * 60)

    # 验证首次问答数据
    first_qa_data = load_json_file("scripts/first_qa_per_conversation.json")
    first_qa_result = validate_qa_data(first_qa_data, "first_qa_per_conversation.json")

    # 验证完整问答数据
    full_qa_data = load_json_file("scripts/live_qa_data_final_v3.json")
    full_qa_result = validate_qa_data(full_qa_data, "live_qa_data_final_v3.json")

    # 总结
    print("\n" + "=" * 60)
    print("数据验证总结")
    print("=" * 60)
    print(f"首次问答数据: {'✅ 有效' if first_qa_result['valid'] else '❌ 无效'}")
    print(f"  - 记录数: {first_qa_result['total_records']}")
    print(f"  - 有效率: {first_qa_result['valid_records']/first_qa_result['total_records']*100:.1f}%")

    print(f"\n完整问答数据: {'✅ 有效' if full_qa_result['valid'] else '❌ 无效'}")
    print(f"  - 记录数: {full_qa_result['total_records']}")
    print(f"  - 有效率: {full_qa_result['valid_records']/full_qa_result['total_records']*100:.1f}%")

    if first_qa_result['valid'] and full_qa_result['valid']:
        print("\n✅ 数据验证通过，可以开始导入")
        return True
    else:
        print("\n❌ 数据验证失败，请检查数据质量")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
