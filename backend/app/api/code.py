"""代码执行 API（Piston 沙箱）"""

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field
from pyston import File as PistonFile
from pyston import PystonClient

from app.core.config import settings
from app.mcp.constants import CODE_SERVER
from app.mcp.mcp_servers.code_exec_mcp.models import CodeExecResponse, CodeExecStage
from app.schemas.response import ApiResponse

router = APIRouter()


class CodeExecuteRequest(BaseModel):
    code: str = Field(..., description="要执行的代码内容")
    language: Literal["python", "javascript", "typescript"] = Field(
        ...,
        description="编程语言：python、javascript、typescript",
    )


@router.post("/execute", summary="执行代码")
async def execute_code(body: CodeExecuteRequest) -> ApiResponse[CodeExecResponse]:
    """通过 Piston 在沙箱中执行代码（需使用 print 等方式输出结果）。"""
    entry = settings.mcp.mcp_servers[CODE_SERVER]
    piston_base_url = entry.env["piston_base_url"]
    client = PystonClient(base_url=piston_base_url)
    try:
        output = await client.execute(
            language=body.language,
            files=[PistonFile(body.code)],
            version="*",
            stdin="",
        )
    finally:
        await client.close_session()

    run_stage = CodeExecStage(
        stdout=output.run_stage.stdout or "",
        stderr=output.run_stage.stdrr or "",
        output=output.run_stage.output or "",
        code=output.run_stage.code,
        signal=output.run_stage.signal,
    )

    compile_stage: CodeExecStage | None = None
    if output.compile_stage:
        compile_stage = CodeExecStage(
            stdout=output.compile_stage.stdout or "",
            stderr=output.compile_stage.stdrr or "",
            output=output.compile_stage.output or "",
            code=output.compile_stage.code,
            signal=output.compile_stage.signal,
        )

    result = CodeExecResponse(
        language=output.langauge or body.language,
        version=output.version or "*",
        run=run_stage,
        compile=compile_stage,
    )
    return ApiResponse.success(data=result, msg="执行完成")
