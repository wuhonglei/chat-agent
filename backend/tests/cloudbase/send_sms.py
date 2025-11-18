import http.client
import os
import json
from dotenv import load_dotenv
load_dotenv()

env_id = os.environ.get('env_id')
phone_number = os.environ.get('phone_number')
conn = http.client.HTTPSConnection(
    f"{env_id}.api.tcloudbasegateway.com")
payload = json.dumps({
    "phone_number": phone_number,
    "email": "",
    "target": "ANY"
})
headers = {
    'Content-Type': 'application/json',
    'Accept': 'application/json'
}
conn.request("POST", "/auth/v1/verification", payload, headers)
res = conn.getresponse()
data = res.read()
print(data.decode("utf-8"))
