"""Model config endpoints for frontend selection."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.schemas.auth import AuthTokenPayload
from app.schemas.response import ApiResponse
from app.services.base_service.model_resolver import list_text_generation_models
from app.utils.auth_deps import get_auth_token_info

router = APIRouter()


class ModelConfigForFe(BaseModel):
    """Sanitized model config for frontend display."""

    model_id: str = Field(description="模型引用（provider/model_name）")
    title: str | None = Field(default=None, description="展示标题")
    description: str | None = Field(default=None, description="说明文案")
    image_support: bool = Field(description="是否支持图片输入")


@router.get("/models")
async def list_models(
    _auth: AuthTokenPayload = Depends(get_auth_token_info),
) -> ApiResponse[list[ModelConfigForFe]]:
    _ = _auth
    model_list = [
        ModelConfigForFe(
            model_id=model_id,
            title=model_config.title,
            description=model_config.description,
            image_support=model_config.image_support,
        )
        for model_id, model_config in list_text_generation_models()
    ]
    return ApiResponse.success(data=model_list, msg="获取模型配置成功")
