"""
测试和风天气 MCP Server
运行方式:
在当前目录下执行:
python test_server.py
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastmcp import Client

from .config import Settings
from .server import (
    make_request,
    mcp,
)

# 模拟环境变量以避免真实 API 调用
config = Settings(
    QWEATHER_API_KEY="test_key_12345", QWEATHER_BASE_URL="https://devapi.qweather.com"
)

mcp_client = Client(mcp)


# ==================== 测试数据 ====================

MOCK_CITY_RESPONSE = {
    "code": "200",
    "location": [
        {
            "name": "北京",
            "id": "101010100",
            "lat": "39.90498",
            "lon": "116.40528",
            "adm2": "北京",
            "adm1": "北京市",
            "country": "中国",
            "tz": "Asia/Shanghai",
            "utcOffset": "+08:00",
            "isDst": "0",
            "type": "city",
            "rank": "10",
            "fxLink": "https://www.qweather.com/weather/beijing-101010100.html",
        }
    ],
    "refer": {"sources": ["QWeather"], "license": ["QWeather Developers License"]},
}

MOCK_WEATHER_NOW_RESPONSE = {
    "code": "200",
    "updateTime": "2025-01-15T16:30+08:00",
    "fxLink": "https://www.qweather.com/weather/beijing-101010100.html",
    "now": {
        "obsTime": "2025-01-15T16:00+08:00",
        "temp": "8",
        "feelsLike": "6",
        "icon": "100",
        "text": "晴",
        "wind360": "315",
        "windDir": "西北风",
        "windScale": "3",
        "windSpeed": "15",
        "humidity": "45",
        "precip": "0.0",
        "pressure": "1020",
        "vis": "30",
        "cloud": "10",
        "dew": "-3",
    },
    "refer": {"sources": ["QWeather"], "license": ["QWeather Developers License"]},
}

MOCK_WEATHER_FORECAST_RESPONSE = {
    "code": "200",
    "updateTime": "2025-01-15T16:30+08:00",
    "fxLink": "https://www.qweather.com/weather/beijing-101010100.html",
    "daily": [
        {
            "fxDate": "2025-01-15",
            "sunrise": "07:36",
            "sunset": "17:24",
            "moonrise": "08:00",
            "moonset": "18:30",
            "moonPhase": "盈凸月",
            "moonPhaseIcon": "803",
            "tempMax": "10",
            "tempMin": "0",
            "iconDay": "100",
            "textDay": "晴",
            "iconNight": "150",
            "textNight": "晴",
            "wind360Day": "315",
            "windDirDay": "西北风",
            "windScaleDay": "1-2",
            "windSpeedDay": "10",
            "wind360Night": "315",
            "windDirNight": "西北风",
            "windScaleNight": "1-2",
            "windSpeedNight": "8",
            "precip": "0.0",
            "uvIndex": "3",
            "humidity": "45",
            "pressure": "1020",
            "vis": "30",
            "cloud": "10",
        }
    ],
    "refer": {"sources": ["QWeather"], "license": ["QWeather Developers License"]},
}

MOCK_WEATHER_ALERTS_RESPONSE = {
    "code": "200",
    "updateTime": "2025-01-15T16:30+08:00",
    "fxLink": "https://www.qweather.com/warning/beijing-101010100.html",
    "warning": [],
    "refer": {"sources": ["QWeather"], "license": ["QWeather Developers License"]},
}

MOCK_AIR_QUALITY_RESPONSE = {
    "code": "200",
    "updateTime": "2025-01-15T16:30+08:00",
    "fxLink": "https://www.qweather.com/air/beijing-101010100.html",
    "now": {
        "pubTime": "2025-01-15T16:00+08:00",
        "aqi": "85",
        "level": "2",
        "category": "良",
        "primary": "PM2.5",
        "pm10": "100",
        "pm2p5": "65",
        "no2": "45",
        "so2": "8",
        "co": "0.6",
        "o3": "50",
    },
    "refer": {"sources": ["QWeather"], "license": ["QWeather Developers License"]},
}


def get_result_data(result):
    data = getattr(result, "data", None)
    if data:
        return data
    return None


# ==================== 测试配置 ====================


def test_config_validation():
    """测试配置验证"""
    assert config.QWEATHER_API_KEY == "test_key_12345"
    assert config.QWEATHER_BASE_URL == "https://devapi.qweather.com"
    assert config.QWEATHER_TIMEOUT == 10


# ==================== 测试 make_request 函数 ====================


@pytest.mark.asyncio
async def test_make_request_success():
    """测试成功的 HTTP 请求"""
    with patch("httpx.AsyncClient") as mock_client:
        mock_response = MagicMock()
        mock_response.json.return_value = MOCK_CITY_RESPONSE
        mock_response.raise_for_status = MagicMock()

        mock_get = AsyncMock(return_value=mock_response)
        mock_client.return_value.__aenter__.return_value.get = mock_get

        result = await make_request("/geo/v2/city/lookup", {"location": "北京"})

        assert result == MOCK_CITY_RESPONSE
        assert result["code"] == "200"


@pytest.mark.asyncio
async def test_make_request_http_error():
    """测试 HTTP 错误处理"""
    with patch("httpx.AsyncClient") as mock_client:
        mock_get = AsyncMock(side_effect=Exception("HTTP 404"))
        mock_client.return_value.__aenter__.return_value.get = mock_get

        with pytest.raises(Exception) as exc_info:
            await make_request("/invalid/endpoint", {})

        assert "请求处理失败" in str(exc_info.value)


# ==================== 测试 search_city 工具 ====================


@pytest.mark.asyncio
async def test_search_city_basic():
    """测试基本城市搜索"""
    with patch("server.make_request", new_callable=AsyncMock) as mock_request:
        mock_request.return_value = MOCK_CITY_RESPONSE

        async with mcp_client:
            result = await mcp_client.call_tool("search_city", {"location": "北京"})
            data = get_result_data(result)
            assert data["code"] == "200"
            assert len(data["location"]) > 0
            assert data["location"][0]["name"] == "北京"


@pytest.mark.asyncio
async def test_search_city_with_filters():
    """测试带过滤条件的城市搜索"""
    with patch("server.make_request", new_callable=AsyncMock) as mock_request:
        mock_request.return_value = MOCK_CITY_RESPONSE

        async with mcp_client as client:
            result = await client.call_tool(
                "search_city",
                {
                    "location": "朝阳",
                    "adm": "北京",
                    "range": "cn",
                    "number": 5,
                    "lang": "zh",
                },
            )

        assert result["code"] == "200"

        # 验证所有参数都被传递
        call_args = mock_request.call_args
        params = call_args[0][1]
        assert params["location"] == "朝阳"
        assert params["adm"] == "北京"
        assert params["range"] == "cn"
        assert params["number"] == 5
        assert params["lang"] == "zh"


@pytest.mark.asyncio
async def test_search_city_error_handling():
    """测试城市搜索错误处理"""
    with patch("server.make_request", new_callable=AsyncMock) as mock_request:
        mock_request.side_effect = Exception("API 错误")

        async with mcp_client as client:
            result = await client.call_tool("search_city", {"location": "北京"})

        assert "error" in result
        assert "API 错误" in result["error"]


# ==================== 测试 get_current_weather 工具 ====================


@pytest.mark.asyncio
async def test_get_current_weather_basic():
    """测试获取实时天气"""
    with patch("server.make_request", new_callable=AsyncMock) as mock_request:
        mock_request.return_value = MOCK_WEATHER_NOW_RESPONSE

        async with mcp_client:
            result = await mcp_client.call_tool("get_current_weather", {"location": "101010100"})
            data = get_result_data(result)

            assert data["code"] == "200"
            assert "now" in data
            assert data["now"]["temp"] == "8"
            assert data["now"]["text"] == "晴"


@pytest.mark.asyncio
async def test_get_current_weather_with_units():
    """测试不同单位的天气查询"""
    with patch("server.make_request", new_callable=AsyncMock) as mock_request:
        mock_request.return_value = MOCK_WEATHER_NOW_RESPONSE

        # 测试公制单位
        async with mcp_client:
            result = await mcp_client.call_tool(
                "get_current_weather", {"location": "101010100", "unit": "m"}
            )
            data = get_result_data(result)
            assert data["code"] == "200"
            assert "now" in data
            assert data["now"]["temp"] == "8"
            assert data["now"]["text"] == "晴"

        # 测试英制单位
        async with mcp_client:
            result = await mcp_client.call_tool(
                "get_current_weather", {"location": "101010100", "unit": "i"}
            )
            data = get_result_data(result)
            assert data["code"] == "200"
            assert "now" in data
            assert data["now"]["temp"] == "8"
            assert data["now"]["text"] == "晴"


# ==================== 测试 get_weather_forecast 工具 ====================


@pytest.mark.asyncio
async def test_get_weather_forecast_3days():
    """测试3天天气预报"""
    with patch("server.make_request", new_callable=AsyncMock) as mock_request:
        mock_request.return_value = MOCK_WEATHER_FORECAST_RESPONSE

        async with mcp_client:
            result = await mcp_client.call_tool(
                "get_weather_forecast", {"location": "101010100", "days": "3d"}
            )
            data = get_result_data(result)
            assert data["code"] == "200"
            assert "daily" in data
            assert isinstance(data["daily"], list)


@pytest.mark.asyncio
async def test_get_weather_forecast_all_periods():
    """测试所有支持的预报天数"""
    valid_days = ["3d", "7d", "10d", "15d", "30d"]

    for days in valid_days:
        with patch("server.make_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = MOCK_WEATHER_FORECAST_RESPONSE

            async with mcp_client:
                result = await mcp_client.call_tool(
                    "get_weather_forecast", {"location": "101010100", "days": days}
                )
                data = get_result_data(result)

                assert data["code"] == "200"
                assert "daily" in data
                assert isinstance(data["daily"], list)


# ==================== 测试 get_weather_alerts 工具 ====================


@pytest.mark.asyncio
async def test_get_weather_alerts_no_alerts():
    """测试无预警情况"""
    with patch("server.make_request", new_callable=AsyncMock) as mock_request:
        mock_request.return_value = MOCK_WEATHER_ALERTS_RESPONSE

        async with mcp_client:
            result = await mcp_client.call_tool("get_weather_alerts", {"location": "101010100"})
            data = get_result_data(result)
            assert data["code"] == "200"
            assert "warning" in data
            assert isinstance(data["warning"], list)
            assert len(data["warning"]) == 0


# ==================== 测试 MCP 工具注册 ====================


@pytest.mark.asyncio
async def test_mcp_tools_registered():
    """测试所有工具是否正确注册到 MCP"""
    async with mcp_client:
        tools = await mcp_client.list_tools()
        tool_names = [tool.name for tool in tools]
        assert len(tool_names) == 5
        assert "search_city" in tool_names
        assert "get_current_weather" in tool_names
        assert "get_weather_forecast" in tool_names
        assert "get_weather_alerts" in tool_names
        assert "get_air_quality" in tool_names


# ==================== 集成测试 ====================


@pytest.mark.asyncio
async def test_weather_workflow():
    """测试完整的天气查询工作流程"""
    with patch("server.make_request", new_callable=AsyncMock) as mock_request:
        mock_request.return_value = MOCK_CITY_RESPONSE
        # 步骤1: 搜索城市
        async with mcp_client:
            result = await mcp_client.call_tool("search_city", {"location": "北京"})
            data = get_result_data(result)
            assert data["code"] == "200"
            assert "location" in data
            assert len(data["location"]) > 0
            assert data["location"][0]["name"] == "北京"


# ==================== 性能和边界测试 ====================


@pytest.mark.asyncio
async def test_concurrent_requests():
    """测试并发请求处理"""
    with patch("server.make_request", new_callable=AsyncMock) as mock_request:
        mock_request.return_value = MOCK_WEATHER_NOW_RESPONSE

        # 同时发起10个请求
        async with mcp_client:
            tasks = [
                mcp_client.call_tool("get_current_weather", {"location": "101010100"})
                for _ in range(10)
            ]
            results = await asyncio.gather(*tasks)

            assert len(results) == 10
            for result in results:
                data = get_result_data(result)
                assert data["code"] == "200"
                assert "now" in data
                assert data["now"]["temp"] == "8"
                assert data["now"]["text"] == "晴"


@pytest.mark.asyncio
async def test_empty_location():
    """测试空位置参数"""
    with patch("server.make_request", new_callable=AsyncMock) as mock_request:
        mock_request.return_value = {"code": "400", "error": "location is required"}
        async with mcp_client:
            result = await mcp_client.call_tool("get_current_weather", {"location": ""})

            # 验证请求被调用
            data = get_result_data(result)
            assert data["code"] == "400"
            assert data["error"] == "location is required"


# ==================== 主函数：直接运行测试 ====================

if __name__ == "__main__":
    """直接运行测试（不使用 pytest）"""

    async def run_all_tests():
        """运行所有测试"""
        print("=" * 60)
        print("和风天气 MCP Server 测试套件")
        print("=" * 60)

        test_results = []

        # 测试1: 配置验证
        print("\n[测试 1] 配置验证...")
        try:
            test_config_validation()
            print("✓ 配置验证通过")
            test_results.append(True)
        except Exception as e:
            print(f"✗ 配置验证失败: {e}")
            test_results.append(False)

        # 测试2: 城市搜索
        print("\n[测试 2] 城市搜索...")
        try:
            await test_search_city_basic()
            print("✓ 城市搜索测试通过")
            test_results.append(True)
        except Exception as e:
            print(f"✗ 城市搜索测试失败: {e}")
            test_results.append(False)

        # 测试3: 实时天气
        print("\n[测试 3] 实时天气查询...")
        try:
            await test_get_current_weather_basic()
            print("✓ 实时天气查询测试通过")
            test_results.append(True)
        except Exception as e:
            print(f"✗ 实时天气查询测试失败: {e}")
            test_results.append(False)

        # 测试4: 天气预报
        print("\n[测试 4] 天气预报查询...")
        try:
            await test_get_weather_forecast_3days()
            print("✓ 天气预报查询测试通过")
            test_results.append(True)
        except Exception as e:
            print(f"✗ 天气预报查询测试失败: {e}")
            test_results.append(False)

        # 测试5: 天气预警
        print("\n[测试 5] 天气预警查询...")
        try:
            await test_get_weather_alerts_no_alerts()
            print("✓ 天气预警查询测试通过")
            test_results.append(True)
        except Exception as e:
            print(f"✗ 天气预警查询测试失败: {e}")
            test_results.append(False)

        # 测试7: 工具注册
        print("\n[测试 7] MCP 工具注册...")
        try:
            await test_mcp_tools_registered()
            print("✓ MCP 工具注册测试通过")
            test_results.append(True)
        except Exception as e:
            print(f"✗ MCP 工具注册测试失败: {e}")
            test_results.append(False)

        # 测试8: 完整工作流
        print("\n[测试 8] 完整天气查询工作流...")
        try:
            await test_weather_workflow()
            print("✓ 完整工作流测试通过")
            test_results.append(True)
        except Exception as e:
            print(f"✗ 完整工作流测试失败: {e}")
            test_results.append(False)

        # 测试9: 并发请求
        print("\n[测试 9] 并发请求处理...")
        try:
            await test_concurrent_requests()
            print("✓ 并发请求测试通过")
            test_results.append(True)
        except Exception as e:
            print(f"✗ 并发请求测试失败: {e}")
            test_results.append(False)

        # 测试10: 空位置参数
        print("\n[测试 10] 空位置参数...")
        try:
            await test_empty_location()
            print("✓ 空位置参数测试通过")
            test_results.append(True)
        except Exception as e:
            print(f"✗ 空位置参数测试失败: {e}")
            test_results.append(False)

        # 汇总结果
        print("\n" + "=" * 60)
        print(f"测试完成: {sum(test_results)}/{len(test_results)} 通过")
        print("=" * 60)

        if all(test_results):
            print("\n🎉 所有测试通过!")
            return 0
        else:
            print("\n⚠️  部分测试失败，请检查上述错误信息")
            return 1

    import sys

    exit_code = asyncio.run(run_all_tests())
    sys.exit(exit_code)
