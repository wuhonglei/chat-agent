from pydantic import BaseModel, Field


class BaseTokenInfo(BaseModel):
    """Base token info"""

    token_type: str | None = Field("Bearer", description="Token type")
    access_token: str = Field(..., description="Access token")
    refresh_token: str = Field(..., description="Refresh token")
    expires_in: int = Field(..., description="Expires in")
    sub: str = Field(..., description="Subject")


class SecretTokenInfo(BaseTokenInfo):
    """Secret token info"""

    user_id: str = Field(..., description="User ID")
    iat: int = Field(..., description="Issue at")
    exp: int = Field(..., description="Expires at")
