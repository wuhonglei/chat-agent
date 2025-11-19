"""
解码 JWT
"""

import jwt
import os
import json
from dotenv import load_dotenv
from pathlib import Path
load_dotenv()


def get_jwt_token(json_path: str) -> str:
    with open(json_path, 'r') as f:
        data = json.load(f)
    return data['verification_id']


def parse_jwt(jwt_token: str) -> dict:
    # Note: Skipping signature verification for testing purposes
    # In production, you should verify with the proper public key
    return jwt.decode(jwt_token, options={"verify_signature": False})


def main():
    json_path = Path(__file__).parent / 'data' / 'new_send_sms.json'
    jwt_token = get_jwt_token(json_path)
    decoded_payload = parse_jwt(jwt_token)
    print("Decoded JWT payload:", decoded_payload)


if __name__ == '__main__':
    main()
