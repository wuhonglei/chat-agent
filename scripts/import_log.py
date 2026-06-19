#!/usr/bin/env python3
"""
Langfuse 导入日志管理工具
"""

import json
import os
import sys
from datetime import datetime
from typing import Any, Optional


LOG_FILE = "scripts/langfuse_import_log.json"


def load_log() -> dict[str, Any]:
    """加载导入日志"""
    try:
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        print(f"⚠️  加载日志失败: {e}", file=sys.stderr)

    return {
        "imports": [],
        "total_imported": 0,
        "total_failed": 0,
        "last_import": None,
    }


def save_log(log_data: dict[str, Any]) -> bool:
    """保存导入日志"""
    try:
        with open(LOG_FILE, 'w', encoding='utf-8') as f:
            json.dump(log_data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"❌ 保存日志失败: {e}", file=sys.stderr)
        return False


def add_import_record(
    data_source: str,
    total_records: int,
    success_count: int,
    failed_count: int,
    duration_seconds: float,
    notes: str = ""
) -> bool:
    """添加导入记录"""
    log_data = load_log()

    record = {
        "timestamp": datetime.now().isoformat(),
        "data_source": data_source,
        "total_records": total_records,
        "success_count": success_count,
        "failed_count": failed_count,
        "success_rate": success_count / total_records * 100 if total_records > 0 else 0,
        "duration_seconds": duration_seconds,
        "records_per_second": total_records / duration_seconds if duration_seconds > 0 else 0,
        "notes": notes,
    }

    log_data["imports"].append(record)
    log_data["total_imported"] += success_count
    log_data["total_failed"] += failed_count
    log_data["last_import"] = record["timestamp"]

    return save_log(log_data)


def print_log_summary() -> None:
    """打印日志摘要"""
    log_data = load_log()

    print("=" * 60)
    print("Langfuse 导入日志摘要")
    print("=" * 60)

    if not log_data["imports"]:
        print("暂无导入记录")
        return

    print(f"总导入次数: {len(log_data['imports'])}")
    print(f"总导入记录: {log_data['total_imported']}")
    print(f"总失败记录: {log_data['total_failed']}")
    print(f"最后导入时间: {log_data['last_import']}")

    print(f"\n最近 5 次导入:")
    for i, record in enumerate(log_data["imports"][-5:]):
        print(f"\n  {i+1}. {record['timestamp']}")
        print(f"     数据源: {record['data_source']}")
        print(f"     总记录: {record['total_records']}")
        print(f"     成功: {record['success_count']}, 失败: {record['failed_count']}")
        print(f"     成功率: {record['success_rate']:.1f}%")
        print(f"     耗时: {record['duration_seconds']:.1f} 秒")
        print(f"     速度: {record['records_per_second']:.1f} 条/秒")
        if record.get("notes"):
            print(f"     备注: {record['notes']}")


def main():
    """主函数"""
    if len(sys.argv) < 2:
        print_log_summary()
        return

    command = sys.argv[1]

    if command == "add":
        # 添加记录
        if len(sys.argv) < 7:
            print("用法: python import_log.py add <data_source> <total> <success> <failed> <duration> [notes]")
            return

        data_source = sys.argv[2]
        total_records = int(sys.argv[3])
        success_count = int(sys.argv[4])
        failed_count = int(sys.argv[5])
        duration_seconds = float(sys.argv[6])
        notes = sys.argv[7] if len(sys.argv) > 7 else ""

        success = add_import_record(
            data_source=data_source,
            total_records=total_records,
            success_count=success_count,
            failed_count=failed_count,
            duration_seconds=duration_seconds,
            notes=notes,
        )

        if success:
            print("✅ 导入记录已添加")
        else:
            print("❌ 添加记录失败")

    elif command == "summary":
        print_log_summary()

    elif command == "clear":
        # 清空日志
        if os.path.exists(LOG_FILE):
            os.remove(LOG_FILE)
            print("✅ 日志已清空")
        else:
            print("日志文件不存在")

    else:
        print(f"未知命令: {command}")
        print("可用命令: add, summary, clear")


if __name__ == "__main__":
    main()
