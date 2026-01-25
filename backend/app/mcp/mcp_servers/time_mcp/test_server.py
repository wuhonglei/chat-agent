"""
Time MCP Server 测试

运行方式:
  pytest app/mcp/mcp_servers/time_mcp/test_server.py -v
  python -m pytest app/mcp/mcp_servers/time_mcp/test_server.py -v

调试方式:
  1. VS Code: 在测试或 server.py 中打断点 → 运行与调试 → 选「Debug Time MCP 测试 (pytest)」
     按提示输入测试名（如 test_get_current_time_with_valid_timezone）或留空跑全部。
  2. 只跑一个测试: pytest app/mcp/mcp_servers/time_mcp/test_server.py -v -k test_format_results
  3. 失败时进入 pdb: pytest app/mcp/mcp_servers/time_mcp/test_server.py -v --pdb
  4. 打印完整输出: pytest app/mcp/mcp_servers/time_mcp/test_server.py -v -s
"""

import re

import pytest
from fastmcp import Client

from app.mcp.mcp_servers.time_mcp.models import TimeResponse
from app.mcp.mcp_servers.time_mcp.server import mcp
from app.mcp.mcp_servers.time_mcp.utils import format_results

mcp_client = Client(mcp)


def get_result_data(result):
    """从 call_tool 结果中提取 data（structured_content）"""
    data = getattr(result, "data", None)
    if data is not None:
        return data
    return None


def _get_field(data, field: str):
    """兼容 data 为 dict 或 Pydantic 模型"""
    if hasattr(data, field):
        return getattr(data, field)
    return data.get(field) if isinstance(data, dict) else None


# ==================== utils.format_results 单元测试 ====================


def test_format_results():
    """测试 format_results 输出包含所有关键字段"""
    resp = TimeResponse(
        current_time="2025-01-25 12:00:00",
        timezone="Asia/Shanghai",
        utc_offset="+0800",
        timestamp=1737784800,
    )
    text = format_results(resp)
    assert "当前时间" in text
    assert "2025-01-25 12:00:00" in text
    assert "时区" in text
    assert "Asia/Shanghai" in text
    assert "UTC 偏移量" in text
    assert "+0800" in text
    assert "Unix 时间戳" in text
    assert "1737784800" in text


# ==================== 通过 MCP Client 的 get_current_time 测试 ====================


@pytest.mark.asyncio
async def test_get_current_time_with_valid_timezone():
    """测试使用有效时区（Asia/Shanghai）获取当前时间"""
    async with mcp_client:
        result = await mcp_client.call_tool(
            "get_current_time", {"timezone": "Asia/Shanghai"}
        )

    data = get_result_data(result)
    assert data is not None

    current_time = _get_field(data, "current_time")
    timezone = _get_field(data, "timezone")
    utc_offset = _get_field(data, "utc_offset")
    timestamp = _get_field(data, "timestamp")

    assert re.match(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$", str(current_time))
    assert timezone == "Asia/Shanghai"
    assert utc_offset == "+0800"
    assert isinstance(timestamp, int)
    assert timestamp > 0


@pytest.mark.asyncio
async def test_get_current_time_with_america_new_york():
    """测试使用 America/New_York 时区"""
    async with mcp_client:
        result = await mcp_client.call_tool(
            "get_current_time", {"timezone": "America/New_York"}
        )

    data = get_result_data(result)
    assert _get_field(data, "timezone") == "America/New_York"
    utc_offset = _get_field(data, "utc_offset")
    assert re.match(r"^[+-]\d{4}$", str(utc_offset))
    assert isinstance(_get_field(data, "timestamp"), int)


@pytest.mark.asyncio
async def test_get_current_time_with_default_timezone():
    """测试不传时区时使用本地时区"""
    async with mcp_client:
        result = await mcp_client.call_tool("get_current_time", {})

    data = get_result_data(result)
    assert data is not None

    current_time = _get_field(data, "current_time")
    timezone = _get_field(data, "timezone")
    timestamp = _get_field(data, "timestamp")

    assert re.match(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$", str(current_time))
    assert timezone
    assert isinstance(timestamp, int)
    assert "无效" not in str(timezone)


@pytest.mark.asyncio
async def test_get_current_time_with_invalid_timezone_fallback():
    """测试无效时区时回退到本地时区"""
    async with mcp_client:
        result = await mcp_client.call_tool(
            "get_current_time", {"timezone": "Invalid/NonExistent/Timezone"}
        )

    data = get_result_data(result)
    assert data is not None
    timezone = _get_field(data, "timezone")

    assert "无效" in str(timezone)
    assert "使用本地时区" in str(timezone)
    assert _get_field(data, "current_time")
    assert isinstance(_get_field(data, "timestamp"), int)


@pytest.mark.asyncio
async def test_get_current_time_result_has_all_fields():
    """测试返回结构包含 current_time、timezone、utc_offset、timestamp"""
    async with mcp_client:
        result = await mcp_client.call_tool("get_current_time", {"timezone": "UTC"})

    data = get_result_data(result)
    assert _get_field(data, "current_time")
    assert _get_field(data, "timezone")
    assert _get_field(data, "utc_offset")
    assert _get_field(data, "timestamp")
    assert "UTC" in str(_get_field(data, "timezone"))


@pytest.mark.asyncio
async def test_mcp_client_call_tool_with_timezone():
    """测试通过 MCP Client 调用 get_current_time 并指定时区"""
    async with mcp_client:
        result = await mcp_client.call_tool(
            "get_current_time", {"timezone": "Europe/London"}
        )

    data = get_result_data(result)
    assert data is not None

    timezone = _get_field(data, "timezone")
    assert timezone == "Europe/London"
    assert _get_field(data, "current_time")
    assert isinstance(_get_field(data, "timestamp"), int)


@pytest.mark.asyncio
async def test_mcp_client_call_tool_without_timezone():
    """测试通过 MCP Client 调用 get_current_time 不传时区（使用默认）"""
    async with mcp_client:
        result = await mcp_client.call_tool("get_current_time", {})

    data = get_result_data(result)
    assert data is not None
    assert _get_field(data, "current_time")
    assert _get_field(data, "timezone")
    assert "无效" not in str(_get_field(data, "timezone"))


@pytest.mark.asyncio
async def test_mcp_tools_registered():
    """测试 get_current_time 已正确注册到 MCP"""
    async with mcp_client:
        tools = await mcp_client.list_tools()

    tool_names = [t.name for t in tools]
    assert "get_current_time" in tool_names


@pytest.mark.asyncio
async def test_mcp_client_invalid_timezone():
    """测试通过 MCP Client 传入无效时区时的回退行为"""
    async with mcp_client:
        result = await mcp_client.call_tool(
            "get_current_time", {"timezone": "Not/A/Real/Zone"}
        )

    data = get_result_data(result)
    assert data is not None
    timezone = _get_field(data, "timezone")
    assert "无效" in str(timezone)
    assert "使用本地时区" in str(timezone)
