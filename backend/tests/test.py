from pydantic import BaseModel, Field


class RefreshTokenRequest(BaseModel):
    """Refresh token request"""

    refresh_token: str = Field(..., description="Refresh token")
    grant_type: str = Field("refresh_token", description="Grant type")


request = RefreshTokenRequest(refresh_token="1234567890", grant_type=None)
print(request)
