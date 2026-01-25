"""
验证短信验证码
文档：https://docs.cloudbase.net/http-api/auth/%E9%AA%8C%E8%AF%81%E7%9F%AD%E4%BF%A1%E3%80%81%E9%82%AE%E7%AE%B1%E9%AA%8C%E8%AF%81%E7%A0%81
验证成功后，会返回 verification_token 用于后续登录，此时并未登录成功
"""

import json
import os

import requests
from dotenv import load_dotenv

load_dotenv()

env_id = os.environ.get("env_id")
phone_number = os.environ.get("phone_number")
verification_id = os.environ.get("verification_id")
verification_code = os.environ.get("verification_code")
url = f"https://{env_id}.api.tcloudbasegateway.com/auth/v1/verification/verify"

payload = json.dumps(
    {"verification_id": verification_id, "verification_code": verification_code}
)
headers = {"Content-Type": "application/json", "Accept": "application/json"}

response = requests.request("POST", url, headers=headers, data=payload)

print(response.text)
