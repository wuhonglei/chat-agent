import os

from app.schemas.config import MCPConfig


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
        # 从模型类访问 model_fields，而不是从实例访问（Pydantic V2.11+）
        for field_name in type(config_obj).model_fields.keys():
            # 获取配置值
            value = getattr(config_obj, field_name, None)
            if value:
                # 字段名即环境变量名，直接使用
                os.environ.setdefault(field_name, str(value))
                injected_count += 1

    if injected_count > 0:
        from app.utils.logger import logger

        logger.info("Injected MCP environment variables", count=injected_count)
