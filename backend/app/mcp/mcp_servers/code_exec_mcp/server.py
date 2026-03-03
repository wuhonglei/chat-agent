"""
Code Exec MCP Server
基于 Piston 提供安全的代码执行服务
支持 Python、Node.js、TypeScript 等语言
Piston 文档: https://github.com/engineer-man/piston
"""

from typing import Literal

from fastmcp import FastMCP
from fastmcp.tools.tool import ToolResult
from pydantic import Field
from pyston import File, PystonClient

from app.mcp.cache import add_response_caching_if_enabled

from .config import config
from .models import CodeExecResponse, CodeExecStage
from .utils import format_results

mcp = FastMCP(name="Code Exec MCP Service")

add_response_caching_if_enabled(mcp, config.cache_config)

SupportedLanguage = Literal["python", "javascript", "typescript"]


@mcp.tool(name="execute_code")
async def execute_code(
    code: str = Field(
        description="要执行的代码内容",
    ),
    language: SupportedLanguage = Field(
        default="python",
        description="执行代码的编程语言，支持：python、javascript、typescript",
    ),
    stdin: str = Field(
        default="",
        description="程序的标准输入（可选）",
    ),
    version: str = Field(
        default="*",
        description="语言版本，默认使用最新版本（*）",
    ),
) -> ToolResult:
    """
    Piston 安全沙箱代码执行服务(必须使用 print 输出结果, 否则无法获取结果)
    """
    client = PystonClient(base_url=config.piston_base_url)
    try:
        output = await client.execute(
            language=language,
            files=[File(code)],
            version=version,
            stdin=stdin,
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
        language=output.langauge or language,
        version=output.version or version,
        run=run_stage,
        compile=compile_stage,
    )

    return ToolResult(
        structured_content=result,
        content=format_results(result),
    )


@mcp.tool(name="list_runtimes")
async def list_runtimes() -> ToolResult:
    """
    列出 Piston 服务器上所有已安装的代码运行时及其版本信息。
    """
    client = PystonClient(base_url=config.piston_base_url)
    try:
        runtimes = await client.runtimes()
    finally:
        await client.close_session()

    lines = ["已安装的运行时："]
    for rt in runtimes:
        aliases = f"（别名: {', '.join(rt.aliases)}）" if rt.aliases else ""
        lines.append(f"  - {rt.language} {rt.version}{aliases}")

    return ToolResult(content="\n".join(lines))


mcp.disable(names={"list_runtimes"}, components={"tool"})
