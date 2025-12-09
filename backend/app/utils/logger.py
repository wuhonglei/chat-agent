"""日志工具模块 - 提供结构化日志和上下文管理

最佳实践：
1. 使用结构化日志，便于日志收集系统解析
2. 记录关键操作和错误，不记录敏感信息
3. 使用上下文绑定（request_id, user_id等）便于追踪
4. 合理使用日志级别
"""

import sys
from contextvars import ContextVar
from typing import Any, Optional

from loguru import logger

# 上下文变量，用于存储请求相关的上下文信息
request_id_var: ContextVar[Optional[str]] = ContextVar(
    "request_id", default=None)
user_id_var: ContextVar[Optional[str]] = ContextVar("user_id", default=None)
client_ip_var: ContextVar[Optional[str]] = ContextVar(
    "client_ip", default=None)


def get_log_context() -> dict[str, Any]:
    """获取当前日志上下文信息"""
    context = {}
    if request_id := request_id_var.get():
        context["request_id"] = request_id
    if user_id := user_id_var.get():
        context["user_id"] = user_id
    if client_ip := client_ip_var.get():
        context["client_ip"] = client_ip
    return context


def log_info(message: str, **kwargs: Any) -> None:
    """记录 INFO 级别日志

    使用结构化字段而不是字符串拼接的原因：
    1. 可查询性：日志收集系统（如 ELK、Loki）可以按字段查询和过滤
    2. 可解析性：便于解析和统计（如按 app_name 分组统计）
    3. 可扩展性：容易添加或移除字段，不影响 message 内容
    4. 一致性：所有日志使用相同的结构化格式
    5. JSON 支持：可以轻松切换到 JSON 格式输出

    Args:
        message: 日志消息（人类可读的描述）
        **kwargs: 结构化字段（键值对，便于查询和统计）

    Example:
        # ✅ 推荐：使用结构化字段
        log_info("Application starting", app_name="MyApp", version="1.0.0")

        # ❌ 不推荐：字符串拼接
        log_info(f"Application {settings.app.name} v{settings.app.version} starting")
    """
    context = get_log_context()
    # 合并上下文和额外字段
    extra = {**context, **kwargs}
    # 使用 loguru 的 extra 参数传递结构化数据
    # 同时为了可读性，也在 message 中包含关键信息
    logger.bind(**extra).info(message)


def log_warning(message: str, **kwargs: Any) -> None:
    """记录 WARNING 级别日志"""
    context = get_log_context()
    extra = {**context, **kwargs}
    logger.bind(**extra).warning(message)


def log_error(message: str, error: Optional[Exception] = None, **kwargs: Any) -> None:
    """记录 ERROR 级别日志

    Args:
        message: 错误消息
        error: 异常对象（可选）
        **kwargs: 额外的上下文信息
    """
    context = get_log_context()
    extra = {**context, **kwargs}
    if error:
        logger.bind(**extra).error(message, exc_info=error)
    else:
        logger.bind(**extra).error(message)


def log_debug(message: str, **kwargs: Any) -> None:
    """记录 DEBUG 级别日志"""
    context = get_log_context()
    extra = {**context, **kwargs}
    logger.bind(**extra).debug(message)


def log_exception(message: str, **kwargs: Any) -> None:
    """记录异常日志（包含完整的堆栈信息）"""
    context = get_log_context()
    extra = {**context, **kwargs}
    logger.bind(**extra).exception(message)


def setup_logger(debug: bool = False) -> None:
    """配置日志系统

    Args:
        debug: 是否启用 DEBUG 级别日志
    """
    logger.remove()  # 移除默认的 handler

    # 配置日志格式
    production_log_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        "<level>{message}</level>"
    )

    debug_log_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        "<level>{message}</level> | "
        "{extra}"
    )

    logger.add(
        sys.stderr,
        level="DEBUG" if debug else "INFO",
        format=debug_log_format if debug else production_log_format,
        serialize=not debug,
    )


# 导出常用的日志函数
__all__ = [
    "log_info",
    "log_warning",
    "log_error",
    "log_debug",
    "log_exception",
    "setup_logger",
    "request_id_var",
    "user_id_var",
    "client_ip_var",
    "get_log_context",
]
