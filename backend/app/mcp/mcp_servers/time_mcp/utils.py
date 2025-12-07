from .models import TimeResponse


def format_results(response: TimeResponse) -> str:
    """
    将时间查询响应格式化为人类可读的文本
    """
    return f"""
当前时间：{response.current_time}
时区：{response.timezone}
UTC 偏移量：{response.utc_offset}
Unix 时间戳：{response.timestamp}
""".strip()
