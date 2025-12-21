from pydantic import BaseModel, Field
from typing import TypedDict, Optional


class MCPConfigForFE(BaseModel):
    id: str = Field(
        description="MCP ID, should be the same value as mcp_config['mcpServers'][id]")
    name: str = Field(description="MCP Name")
    icon: str = Field(description="MCP Icon")
    description: str = Field(description="MCP Description")
    online: Optional[bool] = Field(
        default=False, description="MCP Online Status")


# 定义包含 id,name,icon,description,online 键的 dict 类型
class MCPConfigForFeDict(TypedDict):
    """MCP 配置字典类型定义"""
    id: str
    name: str
    icon: str
    description: str
    online: bool | None
