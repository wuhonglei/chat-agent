from pydantic import BaseModel, Field


class SendSmsRequest(BaseModel):
    """Send SMS request"""

    phone_number: str = Field(..., description="Phone number")
    target: str = Field("ANY", description="Target")


class SendSmsResponse(BaseModel):
    """Send SMS response"""

    verification_id: str = Field(..., description="Verification ID")
    expires_in: int = Field(..., description="Expires in")
    is_user: bool = Field(
        False, description="Is user registered in the cloudbase")


class VerifySmsRequest(BaseModel):
    """Verify SMS request"""

    verification_id: str = Field(..., description="Verification ID")
    verification_code: str = Field(..., description="Verification code")


class VerifySmsRequestFromFrontend(VerifySmsRequest):
    is_user: bool = Field(
        False, description="Is user registered in the cloudbase")


class VerifySmsResponse(BaseModel):
    """Verify SMS response"""

    verification_token: str = Field(..., description="Verification token")
    expires_in: int = Field(..., description="Expires in")


class SigninRequest(BaseModel):
    """Signin request"""

    verification_token: str = Field(..., description="Verification token")


class SigninResponse(BaseModel):
    """Signin response"""

    access_token: str = Field(..., description="Access token")
    refresh_token: str = Field(..., description="Refresh token")
    expires_in: int = Field(..., description="Expires in")
    token_type: str = Field("Bearer", description="Token type")
    sub: str = Field(..., description="User Id in the cloudbase")


class SignupRequest(BaseModel):
    """Signup request"""

    phone_number: str = Field(..., description="Phone number")
    verification_token: str = Field(..., description="Verification token")


class SignupResponse(SigninResponse):
    """Signup response"""
    pass


class RefreshTokenRequest(BaseModel):
    """Refresh token request"""

    refresh_token: str = Field(..., description="Refresh token")


class RefreshTokenResponse(SigninResponse):
    """Refresh token response"""
    pass
