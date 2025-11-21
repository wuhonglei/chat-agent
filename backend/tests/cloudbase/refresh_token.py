"""
刷新 access_token
https://docs.cloudbase.net/http-api/auth/auth-grant-token
注意：
即使当前的 access token 未过期，也可以通过 refresh_token 刷新 access token
刷新后，refresh token 会失效，即使原来的 access token 仍在有效期，也会返回新的 access token。
原来 access token 如果在有效期，也可以正常使用。
"""

import requests
import os
import json
from dotenv import load_dotenv
load_dotenv()

env_id = os.environ.get('env_id')
refresh_token = os.environ.get('refresh_token')

url = f"https://{env_id}.api.tcloudbasegateway.com/auth/v1/token"

payload = json.dumps({
    "grant_type": "refresh_token",
    "refresh_token": refresh_token,
})
headers = {
    'Content-Type': 'application/json',
    'Accept': 'application/json'
}

response = requests.request(
    "POST", url, headers=headers, data=payload, verify=False)

print(response.text)
