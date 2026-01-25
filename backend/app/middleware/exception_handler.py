"""全局异常处理器"""

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from app.schemas.response import ApiResponse
from app.utils.logger import logger


async def validation_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    """处理请求验证异常"""
    assert isinstance(exc, (RequestValidationError, ValidationError))
    errors = exc.errors() if hasattr(exc, "errors") else []
    error_messages: list[str] = []
    for error in errors:
        field = " -> ".join(str(loc) for loc in error.get("loc", []))
        msg = error.get("msg", "验证失败")
        error_messages.append(f"{field}: {msg}")

    error_msg = "; ".join(error_messages) if error_messages else "请求参数验证失败"
    logger.warning(
        "Request validation failed",
        path=request.url.path,
        errors=errors,
    )

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=ApiResponse.error(
            code=422, msg=error_msg, data={"errors": errors}
        ).model_dump(),
    )


async def http_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """处理 HTTPException"""
    from fastapi import HTTPException

    if isinstance(exc, HTTPException):
        status_code = exc.status_code
        detail = exc.detail

        # 根据状态码设置错误码
        error_code = status_code if status_code != 500 else 1

        logger.warning(
            "HTTP exception",
            path=request.url.path,
            status_code=status_code,
            detail=detail,
        )

        return JSONResponse(
            status_code=status_code,
            content=ApiResponse.error(code=error_code, msg=str(detail)).model_dump(),
        )

    # 如果不是 HTTPException，继续抛出（由通用异常处理器处理）
    raise exc


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """处理所有未捕获的异常"""
    logger.exception(
        "Unhandled exception",
        path=request.url.path,
        method=request.method,
        error=exc,
    )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ApiResponse.error(
            code=500, msg="服务器内部错误，请稍后重试"
        ).model_dump(),
    )
