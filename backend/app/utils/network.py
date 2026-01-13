from ipaddress import ip_address

from fastapi import Request


def validate_client_ip(ip: str, keep_private_ip: bool = False) -> str | None:
    """验证IP地址的有效性

    验证规则：
    - 允许私有IP（10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16）- 安全审计需要完整信息
    - 排除无效IP（loopback, multicast, reserved, link-local）

    Args:
        ip: IP地址字符串
        keep_private_ip: 是否保留私有IP，如果为 True，则返回私有IP
    Returns:
        有效的IP地址字符串，如果无效则返回 None
    """
    if not ip:
        return None

    try:
        # 检查是否为有效IP
        ip_obj = ip_address(ip)

        # 排除明显无效的IP（但保留私有IP用于安全审计）
        # loopback: 127.0.0.0/8 - 本地回环，无实际客户端价值
        # multicast: 多播地址，不是真实客户端
        # reserved: 保留地址，未使用
        # link-local: 169.254.0.0/16 - 链路本地，通常是配置失败
        if (
            ip_obj.is_loopback
            or ip_obj.is_multicast
            or ip_obj.is_reserved
            or ip_obj.is_link_local
        ):
            return None

        # 如果不需要保留私有IP，则排除私有IP
        if not keep_private_ip and ip_obj.is_private:
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
        if ip:
            return ip

    # 2. 检查 X-Real-IP（某些代理服务器使用）
    x_real_ip = request.headers.get("X-Real-IP")
    if x_real_ip:
        ip = x_real_ip.strip()
        if ip:
            return ip

    # 3. 使用直接连接的客户端IP
    if request.client and request.client.host:
        ip = request.client.host.strip()
        if ip:
            return ip

    return None


def get_public_client_ip(request: Request) -> str | None:
    """获取有效的客户端IP地址"""
    ip = get_client_ip(request)
    return validate_client_ip(ip, keep_private_ip=False)


def get_audit_client_ip(request: Request) -> str | None:
    """获取可审计的客户端IP地址"""
    ip = get_client_ip(request)
    return validate_client_ip(ip, keep_private_ip=True)
