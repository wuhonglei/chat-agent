from typing import Any

from pydantic import BaseModel, Field


class CodeExecStage(BaseModel):
    """代码执行阶段结果"""

    stdout: str = Field(default="", description="标准输出")
    stderr: str = Field(default="", description="标准错误")
    output: str = Field(default="", description="合并输出（stdout + stderr）")
    code: int | None = Field(default=None, description="退出码")
    signal: Any = Field(default=None, description="终止信号")


class CodeExecResponse(BaseModel):
    """Piston 代码执行响应"""

    language: str = Field(description="执行语言")
    version: str = Field(description="语言版本")
    run: CodeExecStage = Field(description="运行阶段结果")
    compile: CodeExecStage | None = Field(
        default=None, description="编译阶段结果（编译型语言）"
    )
