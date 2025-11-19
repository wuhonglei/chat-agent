"""
获取用户信息
https://docs.cloudbase.net/http-api/auth/user-me
"""

import requests
import os
import json
from dotenv import load_dotenv
load_dotenv()

env_id = os.environ.get('env_id')
access_token = os.environ.get('access_token')
url = f"https://{env_id}.api.tcloudbasegateway.com/auth/v1/user/me"

payload = ""
headers = {
    'Content-Type': 'application/json',
    'Accept': 'application/json',
    'Authorization': f'Bearer {access_token}'
}

response = requests.request("GET", url, headers=headers, data=payload)

print(response.text)
