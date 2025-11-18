import requests
import json
import os
from dotenv import load_dotenv

load_dotenv()

env_id = os.environ.get('env_id')
phone_number = os.environ.get('phone_number')
verification_id = os.environ.get('verification_id')
url = f"https://{env_id}.api.tcloudbasegateway.com/auth/v1/signin"

payload = json.dumps({
    "verification_token": verification_id
})
headers = {
    'Content-Type': 'application/json',
    'Accept': 'application/json'
}

response = requests.request("POST", url, headers=headers, data=payload)

print(response.text)
