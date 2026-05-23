"""日志中间件 - 为每个请求生成 request_id 并绑定到日志上下文"""

import time
from collections.abc import Awaitable, Callable

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.utils.auth_deps import get_user_id_from_token
from app.utils.common import gen_uuid
from app.utils.context import set_request_context
from app.utils.logger import logger
from app.utils.network import get_audit_client_ip

# 不需要记录日志的路径（通常是健康检查、监控等高频低价值请求）
SKIP_LOGGING_PATHS = {
    "/api/health",  # 健康检查
    "/",  # 根路径
}


def should_skip_logging(path: str) -> bool:
    """判断是否应该跳过日志记录"""
    return path in SKIP_LOGGING_PATHS


def set_context_var(request: Request) -> None:
    """设置日志上下文变量

    从请求中提取并设置以下上下文变量：
    - request_id: 请求 ID（从请求头获取或生成新的）
    - user_id: 用户 ID（从 JWT token 中提取）
    - anonymous_user_id: 匿名用户 ID（从请求头获取）
    - client_id: 客户端 ID（从请求头获取）
    - client_ip: 客户端 IP（从请求中提取）

    Args:
        request: FastAPI 请求对象
    """
    request_id = request.headers.get("X-Request-ID") or gen_uuid()
    user_id = get_user_id_from_token(request.headers.get("Authorization"))
    anonymous_user_id = request.headers.get("X-Anonymous-User-ID")
    client_id = request.headers.get("X-Client-ID")
    client_ip = get_audit_client_ip(request)

    set_request_context(
        request_id=request_id,
        user_id=user_id,
        anonymous_user_id=anonymous_user_id if not user_id else None,
        client_id=client_id,
        client_ip=client_ip,
    )


class LoggingMiddleware(BaseHTTPMiddleware):
    """日志中间件

    功能：
    1. 为每个请求生成唯一的 request_id（所有请求都需要）
    2. 将 request_id、client_ip 等绑定到日志上下文（所有请求都需要）
    3. 记录请求开始和结束日志（可配置跳过某些路径）

    注意：
    - request_id 和上下文绑定对所有请求都执行（这是必要的）
    - 但日志记录可以跳过某些高频低价值的端点（如健康检查）

    执行顺序说明（FastAPI 请求处理流程）：
    ┌─────────────────────────────────────────────────────────────┐
    │ 1. 中间件（Middleware）- 最外层                             │
    │    ├─ 设置日志上下文变量（request_id、user_id 等）          │
    │    ├─ 记录 "Request started" 日志                           │
    │    └─ 调用 call_next(request)                               │
    │         ↓                                                    │
    │ 2. 路由匹配（Router Matching）                               │
    │         ↓                                                    │
    │ 3. 依赖注入（Dependencies）- 按声明顺序执行                  │
    │    ├─ Depends(get_jwt_manager) - JWT 管理器                 │
    │    ├─ Depends(require_auth) - 认证验证                      │
    │    │   └─ 内部调用 get_auth_token_info()                    │
    │    │       ├─ 解析并验证 JWT token                          │
    │    │       ├─ 绑定 user_id 到日志上下文                     │
    │    │       └─ 如果 token 过期，自动刷新                     │
    │    ├─ Depends(get_db) - 数据库会话                          │
    │    └─ 其他依赖...                                            │
    │         ↓                                                    │
    │ 4. 路由处理函数（Route Handler）                             │
    │    └─ 执行业务逻辑                                           │
    │         ↓                                                    │
    │ 5. 依赖清理（Dependencies Cleanup）- 按相反顺序执行          │
    │    └─ 如：关闭数据库会话                                    │
    │         ↓                                                    │
    │ 6. 中间件继续（Middleware Continue）                         │
    │    └─ 记录 "Request completed" 日志                          │
    └─────────────────────────────────────────────────────────────┘

    关键点：
    - 中间件在依赖注入之前执行，因此 request_id 在所有依赖中可用
    - 依赖注入中的 user_id 绑定是在路由处理函数执行前完成的
    - 因此路由处理函数中的日志已经包含完整的上下文信息
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        # 设置日志上下文变量
        set_context_var(request)

        # 判断是否需要记录详细日志
        should_log = not should_skip_logging(request.url.path)

        # 记录请求开始（仅对需要记录的请求）
        start_time = time.time()
        if should_log:
            logger.info(
                "Request started",
                method=request.method,
                path=request.url.path,
                query_params=str(request.query_params)
                if request.query_params
                else None,
            )

        # 处理请求
        try:
            response = await call_next(request)

            # 计算处理时间
            process_time = time.time() - start_time

            # 记录请求完成（仅对需要记录的请求）
            if should_log:
                logger.info(
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
            logger.error(
                "Request failed",
                method=request.method,
                path=request.url.path,
                process_time=f"{process_time:.3f}s",
                error=e,
                error_type=type(e).__name__,
            )
            raise
