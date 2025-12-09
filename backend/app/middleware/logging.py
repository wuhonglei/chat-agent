"""日志中间件 - 为每个请求生成 request_id 并绑定到日志上下文"""

import time
from uuid import uuid4

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.utils.logger import (
    client_ip_var,
    log_info,
    request_id_var,
)

# 不需要记录日志的路径（通常是健康检查、监控等高频低价值请求）
SKIP_LOGGING_PATHS = {
    "/api/health",  # 健康检查
    "/",  # 根路径
}


def should_skip_logging(path: str) -> bool:
    """判断是否应该跳过日志记录"""
    return path in SKIP_LOGGING_PATHS


class LoggingMiddleware(BaseHTTPMiddleware):
    """日志中间件

    功能：
    1. 为每个请求生成唯一的 request_id（所有请求都需要）
    2. 将 request_id、client_ip 等绑定到日志上下文（所有请求都需要）
    3. 记录请求开始和结束日志（可配置跳过某些路径）
    4. 在响应头中返回 request_id（便于前端追踪）

    注意：
    - request_id 和上下文绑定对所有请求都执行（这是必要的）
    - 但日志记录可以跳过某些高频低价值的端点（如健康检查）
    """

    async def dispatch(self, request: Request, call_next):
        # 生成 request_id（所有请求都需要，用于追踪）
        request_id = str(uuid4())
        request_id_var.set(request_id)

        # 获取客户端 IP（所有请求都需要，用于安全审计）
        client_ip = request.client.host if request.client else None
        client_ip_var.set(client_ip)

        # 判断是否需要记录详细日志
        should_log = not should_skip_logging(request.url.path)

        # 记录请求开始（仅对需要记录的请求）
        start_time = time.time()
        if should_log:
            log_info(
                "Request started",
                method=request.method,
                path=request.url.path,
                query_params=str(
                    request.query_params) if request.query_params else None,
            )

        # 处理请求
        try:
            response = await call_next(request)

            # 计算处理时间
            process_time = time.time() - start_time

            # 在响应头中添加 request_id（所有请求都需要，便于前端追踪）
            response.headers["X-Request-ID"] = request_id

            # 记录请求完成（仅对需要记录的请求）
            if should_log:
                log_info(
                    "Request completed",
                    method=request.method,
                    path=request.url.path,
                    status_code=response.status_code,
                    process_time=f"{process_time:.3f}s",
                )

            return response

        except Exception as e:
            # 计算处理时间
            process_time = time.time() - start_time

            # 记录请求失败（错误日志总是记录，即使路径在跳过列表中）
            from app.utils.logger import log_error
            log_error(
                "Request failed",
                method=request.method,
                path=request.url.path,
                process_time=f"{process_time:.3f}s",
                error=str(e),
                error_type=type(e).__name__,
            )
            raise


def get_request_id() -> str | None:
    """获取当前请求的 request_id"""
    return request_id_var.get()
