#!/usr/bin/env python3
"""
生成 GitHub webhook 签名，用于测试
"""
import hmac
import hashlib
import json


def generate_github_signature(secret, payload):
    """
    生成 GitHub webhook 的 HMAC-SHA1 签名

    Args:
        secret (str): webhook secret
        payload (str): JSON payload string

    Returns:
        str: GitHub 格式的签名 (sha1=...)
    """
    secret_bytes = secret.encode(
        'utf-8') if isinstance(secret, str) else secret
    payload_bytes = payload.encode(
        'utf-8') if isinstance(payload, str) else payload

    signature = hmac.new(secret_bytes, payload_bytes, hashlib.sha1)
    return f"sha1={signature.hexdigest()}"


def main():
    # 从环境变量获取 secret，或者使用默认值
    import os

    # 尝试加载 .env 文件（如果存在）
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass  # 如果没有 dotenv 包，跳过

    secret = os.getenv('WEBHOOK_SECRET', 'your_webhook_secret_here')

    # 读取 payload 文件
    with open('webhook_test_payload.json', 'r', encoding='utf-8') as f:
        payload_data = json.load(f)

    # 转换为 JSON 字符串（确保格式与 GitHub 一致）
    payload_json = json.dumps(payload_data, separators=(',', ':'))

    # 生成签名
    signature = generate_github_signature(secret, payload_json)

    print("GitHub Webhook 测试签名生成器")
    print("=" * 40)
    print(f"Secret: {secret}")
    print(f"Signature: {signature}")
    print()
    print("Postman Headers:")
    print("X-Github-Event: create")
    print(f"X-Hub-Signature: {signature}")
    print("Content-Type: application/json")
    print()
    print("使用方法：")
    print("1. 将 signature 添加到 Postman 的 X-Hub-Signature header")
    print("2. 将 webhook_test_payload.json 的内容作为请求体")
    print("3. 发送 POST 请求到 http://localhost:9000/postreceive")


if __name__ == "__main__":
    main()
