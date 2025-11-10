import asyncio
from fastmcp import Client

from .server import mcp
from pprint import pprint


client = Client(mcp)


async def test_python_code_exec():
    async with client:
        result = await client.call_tool("python_code_exec", {
            "code": "import math\nprint(math.sqrt(16))"
        })
    pprint(result.data)


if __name__ == "__main__":
    asyncio.run(test_python_code_exec())
