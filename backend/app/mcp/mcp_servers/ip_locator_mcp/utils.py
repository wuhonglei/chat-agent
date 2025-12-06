from .models import IPLocatorResponse


def format_results(response: IPLocatorResponse) -> str:
    """
    Format the response to a human-readable string
    """
    return f"""
请求状态: {response.status}
国家: {response.country}
国家代码: {response.countryCode}
地区代码: {response.region}
地区名称: {response.regionName}
城市: {response.city}
经度(lat): {response.lon:.6f}
纬度(lon): {response.lat:.6f}
时区: {response.timezone}
""".strip()
