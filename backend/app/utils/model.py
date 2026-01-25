import json
from typing import Any

from pydantic import BaseModel


def get_model_extra_body(think_mode: bool) -> dict[str, Any]:
    """
    获取模型额外参数

    有些模型同时支持思考模式和非思考模式，需要通过 extra_body 来控制模型是否启用思考模式
    """
    if not think_mode:
        return {}

    return {
        # 兼容 qwen-plus 模型 (https://bailian.console.aliyun.com/?spm=5176.29597918.J_SEsSjsNv72yRuRFS2VknO.2.4dec7b084pEDSL&tab=model#/model-market/detail/qwen-plus)
        "enable_thinking": True,
        "thinking": {
            # 兼容 deepseek-reasoner 模型 (https://api-docs.deepseek.com/guides/thinking_mode)
            "type": "enabled"
        },
    }


def format_sse_message(msg_type: str, data: Any | None = None) -> str:
    """Format SSE (Server-Sent Events) message

    注意：此方法仅用于格式化SSE消息，不负责状态更新。
    状态更新由各个agent自行管理。
    """
    if data is None:
        return f"data: {json.dumps({'type': msg_type, 'data': {}}, ensure_ascii=False)}\n\n"

    # 如果 data 是 BaseModel
    if isinstance(data, BaseModel):
        data = data.model_dump(mode="json")

    return (
        f"data: {json.dumps({'type': msg_type, 'data': data}, ensure_ascii=False)}\n\n"
    )
