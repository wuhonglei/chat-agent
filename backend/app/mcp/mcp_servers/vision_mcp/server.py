"""Vision MCP Service：按问题分析一张图片。"""

from __future__ import annotations

from fastmcp import FastMCP
from fastmcp.tools.tool import ToolResult
from pydantic import Field

from app.mcp.mcp_servers.file_mcp.base import ToolContext, to_fastmcp_tool_result
from app.mcp.mcp_servers.vision_mcp.analyze import (
    VISION_ANALYZE_DESCRIPTION,
    VisionAnalyzeTool,
)

mcp = FastMCP(name="Vision MCP Service")

_analyze = VisionAnalyzeTool()


@mcp.tool(name="analyze", description=VISION_ANALYZE_DESCRIPTION)
async def analyze(
    image_url: str = Field(
        ...,
        description=(
            "Image to analyze. One of: http/https URL, virtual file path "
            "(e.g. /mnt/user-data/uploads/photo.png), or data:image/...;base64,... URL"
        ),
    ),
    question: str = Field(
        ...,
        description="Question or instruction about the image",
    ),
) -> ToolResult:
    """Analyze an image and answer the question."""
    ctx = ToolContext()
    result = await _analyze.execute(
        {"image_url": image_url, "question": question},
        ctx,
    )
    return to_fastmcp_tool_result(result)
