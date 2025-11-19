from typing import Any

from pydantic import BaseModel, Field


class CloudBaseTokenInfo(BaseModel):
    """CloudBase token info"""

    token_type: str = Field(..., description="Token type")
    access_token: str = Field(..., description="Access token")
    refresh_token: str = Field(..., description="Refresh token")
    expires_in: int = Field(..., description="Expires in")
    sub: str = Field(..., description="Subject")


class SecretTokenInfo(CloudBaseTokenInfo):
    """Secret token info"""
    user_id: str = Field(..., description="User ID")
    issue_at: int = Field(..., description="Issue at")
    expires_at: int = Field(..., description="Expires at")
