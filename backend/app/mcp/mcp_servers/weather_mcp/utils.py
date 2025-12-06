from typing import Dict, Any
import httpx
from .config import config


async def make_request(endpoint: str, params: Dict[str, Any]) -> dict[str, Any]:
    """发送 HTTP 请求到和风天气 API"""
    url = f"{config.QWEATHER_BASE_URL}{endpoint}"
    params["key"] = config.QWEATHER_API_KEY

    async with httpx.AsyncClient(timeout=config.QWEATHER_TIMEOUT) as client:
        try:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            if data.get("code") != "200":
                raise Exception(data)
            return data
        except httpx.HTTPError as e:
            raise Exception(f"HTTP 请求失败: {e}")
        except Exception as e:
            raise Exception(f"请求处理失败: {e}")
