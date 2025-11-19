"""
发送短信验证码
文档: https://docs.cloudbase.net/http-api/auth/%E5%8F%91%E9%80%81%E7%9F%AD%E4%BF%A1%E3%80%81%E9%82%AE%E7%AE%B1%E9%AA%8C%E8%AF%81%E7%A0%81
注意：如果是已经注册的用户,返回的数据中会有 is_user 字段，且值为 true
"""

import requests
import os
import json
from dotenv import load_dotenv
load_dotenv()

env_id = os.environ.get('env_id')
phone_number = os.environ.get('phone_number')

url = f"https://{env_id}.api.tcloudbasegateway.com/auth/v1/verification"

payload = json.dumps({
    "phone_number": phone_number,
    "target": "ANY"
})
headers = {
    'Content-Type': 'application/json',
    'Accept': 'application/json'
}

response = requests.request("POST", url, headers=headers, data=payload)

print(response.text)
