"""日志工具模块 - 提供结构化日志和上下文管理

最佳实践：
1. 使用结构化日志，便于日志收集系统解析
2. 记录关键操作和错误，不记录敏感信息
3. 使用上下文绑定（request_id, user_id等）便于追踪
4. 合理使用日志级别
"""

import json
import sys
from contextvars import ContextVar
from typing import Any

from loguru import logger as _loguru_logger

try:
    from loguru import Message
except ImportError:
    Message = Any  # type: ignore

from app.utils.time import format_datetime_to_iso8601


def _make_json_serializable(obj: Any) -> Any:
    """递归地将对象转换为 JSON 可序列化的格式

    将异常对象、datetime 对象等不可序列化的对象转换为字符串
    """
    if isinstance(obj, Exception):
        return {
            "type": obj.__class__.__name__,
            "message": str(obj),
        }
    elif isinstance(obj, dict):
        return {key: _make_json_serializable(value) for key, value in obj.items()}
    elif isinstance(obj, list | tuple):
        return [_make_json_serializable(item) for item in obj]
    elif isinstance(obj, str | int | float | bool | type[None]):
        return obj
    else:
        # 对于其他不可序列化的对象，转换为字符串
        try:
            json.dumps(obj)
            return obj
        except (TypeError, ValueError):
            return str(obj)


# 上下文变量，用于存储请求相关的上下文信息
request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
user_id_var: ContextVar[str | None] = ContextVar("user_id", default=None)
anonymous_user_id_var: ContextVar[str | None] = ContextVar(
    "anonymous_user_id", default=None
)
client_id_var: ContextVar[str | None] = ContextVar("client_id", default=None)
client_ip_var: ContextVar[str | None] = ContextVar("client_ip", default=None)


def production_sink(message: Message) -> None:
    """生产环境自定义 sink，输出精简的 JSON 格式日志

    移除的冗余字段：
    - text: 格式化的文本（JSON 日志中不需要）
    - elapsed: 时间间隔（通常不需要）
    - process.name, thread.name: 进程/线程名称（通常不需要）
    - level.icon: 级别图标（JSON 中不需要）
    - time.repr: 时间字符串表示（只需要 timestamp）
    - file.path: 完整文件路径（只需要文件名）

    保留的必要字段：
    - timestamp: 时间戳（ISO 8601 格式，系统本地时区，便于阅读和理解）
    - level: 日志级别
    - message: 日志消息
    - location: 代码位置（格式：file:line:function，便于快速定位问题）
    - extra: 上下文信息（request_id, user_id 等）
    - exception: 异常信息（如果有）

    时间戳格式说明：
    - 使用 ISO 8601 格式字符串（如 "2024-01-01T12:00:00.123456+08:00"）
    - 使用系统本地时区，便于本地开发和调试时直观理解时间
    - 包含微秒精度，便于精确排序和调试
    - 人类可读，同时所有日志系统都支持解析
    """
    record = message.record
    # 构建精简的日志记录
    # 合并代码位置信息为紧凑格式：module:function:line（与 debug_log_format 保持一致）
    location = f"{record['name']}:{record['function']}:{record['line']}"

    serialized = {
        "timestamp": format_datetime_to_iso8601(record["time"]),
        "level": record["level"].name,
        "message": record["message"],
        "location": location,
    }

    # 添加 extra 字段（包含 request_id, user_id, client_ip 等上下文信息）
    # 需要将 extra 中的不可序列化对象（如异常对象）转换为可序列化格式
    if record["extra"]:
        serialized["extra"] = _make_json_serializable(record["extra"])

    # 添加异常信息（如果有）
    if record["exception"]:
        # 将 traceback 转换为字符串以便 JSON 序列化
        traceback_str = None
        try:
            traceback_str = str(record["exception"].traceback)
        except Exception:
            pass

        exception_info = {
            "type": record["exception"].type.__name__
            if record["exception"].type
            else "Unknown",
            "value": str(record["exception"].value),
        }
        if traceback_str:
            exception_info["traceback"] = traceback_str
        serialized["exception"] = exception_info  # type: ignore

    # 输出 JSON 格式
    sys.stderr.write(json.dumps(serialized, ensure_ascii=False) + "\n")


def get_log_context() -> dict[str, Any]:
    """获取当前日志上下文信息"""
    context = {}
    if request_id := request_id_var.get():
        context["request_id"] = request_id
    if user_id := user_id_var.get():
        context["user_id"] = user_id
    if anonymous_user_id := anonymous_user_id_var.get():
        context["anonymous_user_id"] = anonymous_user_id
    if client_id := client_id_var.get():
        context["client_id"] = client_id
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
    # depth=1 跳过当前包装函数，记录实际调用者的位置信息
    _loguru_logger.opt(depth=1).bind(**extra).info(message)


def log_warning(message: str, **kwargs: Any) -> None:
    """记录 WARNING 级别日志"""
    context = get_log_context()
    extra = {**context, **kwargs}
    # depth=1 跳过当前包装函数，记录实际调用者的位置信息
    _loguru_logger.opt(depth=1).bind(**extra).warning(message)


def log_error(message: str, error: Exception | None = None, **kwargs: Any) -> None:
    """记录 ERROR 级别日志

    Args:
        message: 错误消息
        error: 异常对象（可选）
        **kwargs: 额外的上下文信息
    """
    context = get_log_context()
    extra = {**context, **kwargs}
    # depth=1 跳过当前包装函数，记录实际调用者的位置信息
    if error:
        _loguru_logger.opt(depth=1).bind(**extra).error(message, exc_info=error)
    else:
        _loguru_logger.opt(depth=1).bind(**extra).error(message)


def log_debug(message: str, **kwargs: Any) -> None:
    """记录 DEBUG 级别日志"""
    context = get_log_context()
    extra = {**context, **kwargs}
    # depth=1 跳过当前包装函数，记录实际调用者的位置信息
    _loguru_logger.opt(depth=1).bind(**extra).debug(message)


def log_exception(message: str, **kwargs: Any) -> None:
    """记录异常日志（包含完整的堆栈信息）"""
    context = get_log_context()
    extra = {**context, **kwargs}
    # depth=1 跳过当前包装函数，记录实际调用者的位置信息
    _loguru_logger.opt(depth=1).bind(**extra).exception(message)


class LoggerWrapper:
    """日志包装器，自动添加上下文信息

    使用方式：
        from app.utils.logger import logger
        logger.info("消息", key="value")
        logger.warning("警告")
        logger.error("错误", error=exception)
        logger.debug("调试信息")
        logger.exception("异常信息")
    """

    def info(self, message: str, **kwargs: Any) -> None:
        """记录 INFO 级别日志

        Args:
            message: 日志消息
            **kwargs: 结构化字段（键值对，便于查询和统计）
        """
        context = get_log_context()
        extra = {**context, **kwargs}
        # depth=1 跳过当前包装函数，记录实际调用者的位置信息
        _loguru_logger.opt(depth=1).bind(**extra).info(message)

    def warning(self, message: str, **kwargs: Any) -> None:
        """记录 WARNING 级别日志"""
        context = get_log_context()
        extra = {**context, **kwargs}
        _loguru_logger.opt(depth=1).bind(**extra).warning(message)

    def error(
        self, message: str, error: Exception | None = None, **kwargs: Any
    ) -> None:
        """记录 ERROR 级别日志

        Args:
            message: 错误消息
            error: 异常对象（可选）
            **kwargs: 额外的上下文信息
        """
        context = get_log_context()
        extra = {**context, **kwargs}
        if error:
            _loguru_logger.opt(depth=1).bind(**extra).error(message, exc_info=error)
        else:
            _loguru_logger.opt(depth=1).bind(**extra).error(message)

    def debug(self, message: str, **kwargs: Any) -> None:
        """记录 DEBUG 级别日志"""
        context = get_log_context()
        extra = {**context, **kwargs}
        _loguru_logger.opt(depth=1).bind(**extra).debug(message)

    def exception(self, message: str, **kwargs: Any) -> None:
        """记录异常日志（包含完整的堆栈信息）"""
        context = get_log_context()
        extra = {**context, **kwargs}
        _loguru_logger.opt(depth=1).bind(**extra).exception(message)


# 创建 logger 实例供外部使用
logger = LoggerWrapper()


def setup_logger(debug: bool = False) -> None:
    """配置日志系统

    Args:
        debug: 是否启用 DEBUG 级别日志
    """
    _loguru_logger.remove()  # 移除默认的 handler

    if debug:
        debug_log_format = (
            "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
            "<level>{message}</level> | "
            "{extra}"
        )
        # 调试模式：使用格式化的文本输出
        _loguru_logger.add(
            sys.stderr,
            level="DEBUG",
            format=debug_log_format,
        )
    else:
        # 生产模式：使用自定义 sink 输出精简的 JSON
        _loguru_logger.add(
            production_sink,
            level="INFO",
            serialize=False,  # 不使用默认序列化，使用自定义 sink
        )


# 导出 logger 对象和常用工具
__all__ = [
    "logger",  # logger 对象，通过 logger.info, logger.warning 等方式使用
    "setup_logger",
    "request_id_var",
    "user_id_var",
    "anonymous_user_id_var",
    "client_ip_var",
    "get_log_context",
    # 保留旧函数以保持向后兼容（可选，如果不需要可以删除）
    "log_info",
    "log_warning",
    "log_error",
    "log_debug",
    "log_exception",
]
