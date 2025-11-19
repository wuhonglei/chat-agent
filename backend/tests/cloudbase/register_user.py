"""
注册新用户

"""

import requests
import os
import json
from dotenv import load_dotenv
load_dotenv()

env_id = os.environ.get('env_id')
phone_number = os.environ.get('phone_number')
verification_token = os.environ.get('verification_token')
url = f"https://{env_id}.api.tcloudbasegateway.com/auth/v1/signup"

payload = json.dumps({
    "phone_number": phone_number,
    "verification_token": verification_token,
})
headers = {
    'Content-Type': 'application/json',
    'Accept': 'application/json'
}

response = requests.request("POST", url, headers=headers, data=payload)

print(response.text)
