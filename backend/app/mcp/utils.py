import os
from app.models.config import MCPConfig
from loguru import logger


def inject_mcp_env_vars(mcp_config: MCPConfig) -> None:
    """
    从 MCPConfig 对象中提取配置并注入到环境变量中
    """
    mcp_configs = [
        mcp_config.tavily_mcp,
        mcp_config.weather_mcp,
        mcp_config.confluence_mcp,
    ]

    injected_count = 0
    for config_obj in mcp_configs:
        # 使用 Pydantic 模型的字段信息，只遍历定义的字段
        for field_name in config_obj.model_fields.keys():
            # 获取配置值
            value = getattr(config_obj, field_name, None)
            if value:
                # 字段名即环境变量名，直接使用
                os.environ.setdefault(field_name, str(value))
                injected_count += 1

    if injected_count > 0:
        logger.info(f"已从 config.yaml 注入 {injected_count} 个 MCP 环境变量")
