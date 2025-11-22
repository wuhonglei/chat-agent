"""通用装饰器工具"""

import functools
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from fastapi import HTTPException
from loguru import logger

# 类型变量，用于保持函数签名
F = TypeVar("F", bound=Callable[..., Any])


def handle_api_exceptions(
    operation_name: str | None = None,
    default_status_code: int = 500,
    default_message: str | None = None,
    log_exception: bool = True,
) -> Callable[[F], F]:
    """
    装饰器：统一处理 API 路由中的异常

    功能：
    1. 自动捕获 HTTPException 并重新抛出
    2. 捕获其他异常，记录日志并转换为 HTTPException
    3. 支持自定义操作名称和错误消息

    Args:
        operation_name: 操作名称（用于日志），默认使用函数名
        default_status_code: 默认 HTTP 状态码，默认 500
        default_message: 默认错误消息，默认 "操作失败"
        log_exception: 是否记录异常详情（exc_info），默认 True

    Examples:
        ```python
        @router.post("/upload")
        @handle_api_exceptions(operation_name="文件上传", default_message="文件上传失败")
        async def upload_file(file: UploadFile):
            # 业务逻辑
            pass
        ```

    注意：
    - 对于需要资源清理的场景（如临时文件），建议在函数内部使用 try-finally
    - HTTPException 会被直接重新抛出，不会被转换
    """

    def decorator(func: F) -> F:
        # 获取操作名称
        op_name = operation_name or func.__name__
        error_msg = default_message or "操作失败"

        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return await func(*args, **kwargs)
            except HTTPException:
                # HTTPException 直接重新抛出，不进行处理
                raise
            except Exception as e:
                # 记录异常日志
                # 使用 % 格式化避免异常消息中的花括号被解析为格式化占位符
                if log_exception:
                    logger.exception("%s失败", op_name)
                else:
                    logger.error("%s失败: %s", op_name, str(e))

                # 转换为 HTTPException
                raise HTTPException(
                    status_code=default_status_code,
                    detail=error_msg if not str(
                        e) else f"{error_msg}: {str(e)}"
                )

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return func(*args, **kwargs)
            except HTTPException:
                raise
            except Exception as e:
                # 使用 % 格式化避免异常消息中的花括号被解析为格式化占位符
                if log_exception:
                    logger.exception("%s失败", op_name)
                else:
                    logger.error("%s失败: %s", op_name, str(e))

                raise HTTPException(
                    status_code=default_status_code,
                    detail=error_msg
                )

        # 检查是否是协程函数
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore
        else:
            return sync_wrapper  # type: ignore

    return decorator


def handle_api_exceptions_with_cleanup(
    cleanup_func: Callable[[], Any] | None = None,
    operation_name: str | None = None,
    default_status_code: int = 500,
    default_message: str | None = None,
) -> Callable[[F], F]:
    """
    装饰器：处理 API 异常并执行清理操作

    适用于需要资源清理的场景（如临时文件、数据库连接等）

    Args:
        cleanup_func: 清理函数，会在 finally 块中执行
        operation_name: 操作名称
        default_status_code: 默认 HTTP 状态码
        default_message: 默认错误消息

    Examples:
        ```python
        def cleanup_temp_file(file_path: Path):
            if file_path.exists():
                file_path.unlink()

        @router.post("/upload")
        @handle_api_exceptions_with_cleanup(
            cleanup_func=lambda: cleanup_temp_file(temp_file_path),
            operation_name="文件上传"
        )
        async def upload_file(file: UploadFile):
            # 业务逻辑
            pass
        ```
    """

    def decorator(func: F) -> F:
        op_name = operation_name or func.__name__
        error_msg = default_message or "操作失败"

        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return await func(*args, **kwargs)
            except HTTPException:
                raise
            except Exception as e:
                # 使用 % 格式化避免异常消息中的花括号被解析为格式化占位符
                logger.exception("%s失败", op_name)
                raise HTTPException(
                    status_code=default_status_code,
                    detail=error_msg if not str(
                        e) else f"{error_msg}: {str(e)}"
                )
            finally:
                # 执行清理操作
                if cleanup_func:
                    try:
                        cleanup_func()
                    except Exception as cleanup_error:
                        logger.warning("%s清理失败: %s", op_name,
                                       str(cleanup_error))

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return func(*args, **kwargs)
            except HTTPException:
                raise
            except Exception as e:
                # 使用 % 格式化避免异常消息中的花括号被解析为格式化占位符
                logger.exception("%s失败", op_name)
                raise HTTPException(
                    status_code=default_status_code,
                    detail=error_msg if not str(
                        e) else f"{error_msg}: {str(e)}"
                )
            finally:
                if cleanup_func:
                    try:
                        cleanup_func()
                    except Exception as cleanup_error:
                        logger.warning("%s清理失败: %s", op_name,
                                       str(cleanup_error))

        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore
        else:
            return sync_wrapper  # type: ignore

    return decorator
