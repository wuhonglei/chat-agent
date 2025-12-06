from fastapi import Request
from ipaddress import ip_address


def validate_client_ip(ip: str) -> str | None:
    """验证IP地址的有效性"""
    try:
        # 检查是否为有效IP
        ip_obj = ip_address(ip)

        # 排除私有IP和内网IP
        if ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_link_local:
            return None

        # 排除保留IP段
        if ip_obj.is_reserved or ip_obj.is_multicast:
            return None

        return str(ip_obj)
    except ValueError:
        return None


def get_client_ip(request: Request) -> str | None:
    """
    获取客户端真实IP地址

    优先级：
    1. X-Forwarded-For 头（取第一个IP，适用于多级代理）
    2. X-Real-IP 头（某些代理服务器使用）
    3. request.client.host（直接连接的客户端IP）

    Returns:
        str: 客户端IP地址字符串

    Raises:
        ValueError: 如果无法获取有效的IP地址
    """
    # 1. 优先检查 X-Forwarded-For（适用于多级代理）
    x_forwarded_for = request.headers.get("X-Forwarded-For")
    if x_forwarded_for:
        # 分割并取第一个IP，去除空格
        ip = x_forwarded_for.split(",")[0].strip()
        if ip and validate_client_ip(ip):
            return ip

    # 2. 检查 X-Real-IP（某些代理服务器使用）
    x_real_ip = request.headers.get("X-Real-IP")
    if x_real_ip:
        ip = x_real_ip.strip()
        if ip and validate_client_ip(ip):
            return ip

    # 3. 使用直接连接的客户端IP
    if request.client and request.client.host:
        ip = request.client.host.strip()
        if ip and validate_client_ip(ip):
            return ip

    return None
