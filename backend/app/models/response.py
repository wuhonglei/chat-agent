"""统一响应格式模型"""

from typing import Generic, TypeVar, Optional
from pydantic import BaseModel, Field

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    """统一的API响应格式

    格式: { code, msg, data }
    """
    code: int = Field(..., description="响应状态码，0表示成功，非0表示失败")
    msg: str = Field(..., description="响应消息")
    data: Optional[T] = Field(None, description="响应数据")

    @classmethod
    def success(cls, data: T = None, msg: str = "操作成功") -> "ApiResponse[T]":
        """创建成功响应"""
        return cls(code=0, msg=msg, data=data)

    @classmethod
    def error(cls, code: int = 1, msg: str = "操作失败", data: T = None) -> "ApiResponse[T]":
        """创建错误响应"""
        return cls(code=code, msg=msg, data=data)
