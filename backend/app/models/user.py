from pydantic import BaseModel, Field
from datetime import datetime


class User(BaseModel):
    """User model"""

    id: str = Field(..., description="User ID")
    name: str = Field(..., description="User name")
    email: str = Field(..., description="User email")
    avatar: str = Field(..., description="User avatar")
    created_at: datetime = Field(..., description="Created at")
    updated_at: datetime = Field(..., description="Updated at")
