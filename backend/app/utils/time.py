import time


def get_current_time() -> float:
    """获取当前时间
    Returns:
        float: 当前时间戳
    """
    return time.time()


def get_time_duration(start_time: float) -> float:
    """获取时间差
    Args:
        start_time: 开始时间
    Returns:
        float: 时间差
    """
    return round(time.time() - start_time, 2)
