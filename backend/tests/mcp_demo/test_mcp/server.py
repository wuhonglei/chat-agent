import asyncio
import json
from fastmcp import FastMCP
from fastmcp.tools.tool import ToolResult
from fastmcp import Client
from fastmcp.client.transports import FastMCPTransport

from pydantic import BaseModel

mcp = FastMCP("test-mcp")


@mcp.tool(name="test_tool")
def test_tool(name: str) -> str:
    return f"Hello, {name}!"


@mcp.tool(name="test_tool2")
def test_tool2(name: str) -> dict[str, any]:
    return {"name": "John", "age": 18}


@mcp.tool(name="test_tool3")
def test_tool3(name: str) -> list[str]:
    return ["Hello", "World"]


class TestTool4(BaseModel):
    name: str
    age: int


@mcp.tool(name="test_tool4")
def test_tool4(name: str) -> TestTool4:
    data = TestTool4(name="John", age=18)
    return ToolResult(structured_content=data, content=['12', '34'])


async def main():
    client = Client(transport=FastMCPTransport(mcp))
    async with client:
        result = await client.call_tool("test_tool", {"name": "John"})
        result = await client.call_tool("test_tool2", {"name": "John"})
        result = await client.call_tool("test_tool3", {"name": "John"})
        result = await client.call_tool("test_tool4", {"name": "John"})
        pass
        print(result)

if __name__ == "__main__":
    # mcp.run(transport="stdio")
    asyncio.run(main())  # 异步运行
