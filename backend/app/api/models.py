"""Model config endpoints for frontend selection."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.core.config import settings
from app.schemas.auth import AuthTokenPayload
from app.schemas.response import ApiResponse
from app.utils.auth_deps import get_auth_token_info

router = APIRouter()


class ModelConfigForFe(BaseModel):
    """Sanitized model config for frontend display."""

    id: str = Field(description="Model ID")
    model_name: str = Field(description="Model name for display")
    image_support: bool = Field(description="Whether this model supports image input")


@router.get("/models")
async def list_models(
    _auth: AuthTokenPayload = Depends(get_auth_token_info),
) -> ApiResponse[list[ModelConfigForFe]]:
    _ = _auth
    model_list = [
        ModelConfigForFe(
            id=model_id,
            model_name=model_config.model_name,
            image_support=model_config.image_support,
        )
        for model_id, model_config in settings.model_map.items()
    ]
    return ApiResponse.success(data=model_list, msg="获取模型配置成功")
