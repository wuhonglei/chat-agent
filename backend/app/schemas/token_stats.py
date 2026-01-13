"""Token 统计相关的 Schema 定义"""

from pydantic import BaseModel, Field


class TokenUsage(BaseModel):
    """Token 使用量统计"""

    prompt_tokens: int = Field(..., description="输入 token 数量")
    completion_tokens: int = Field(..., description="输出 token 数量")
    total_tokens: int = Field(..., description="总 token 数量")


class BaseTokenStats(BaseModel):
    """Token 统计基类"""

    agent_name: str = Field(..., description="Agent 名称")
    model_name: str = Field(..., description="使用的模型名称")
    think_mode: bool = Field(..., description="是否使用思考模式")
    model_limit: int = Field(..., description="模型限制的 token 数量")
    token_usage: TokenUsage = Field(..., description="Token 使用量")


class MCPToolsTokenStats(BaseTokenStats):
    """MCP 工具调用的 Token 统计"""

    tool_call_count: int = Field(..., description="被调用的工具数量")
    tool_call_names: list[str] = Field(..., description="被调用的工具名称列表")
    tool_definition_tokens: int = Field(..., description="工具定义 token 数量")


class ComponentToolsTokenStats(BaseTokenStats):
    """组件工具调用的 Token 统计"""

    tool_call_count: int = Field(..., description="被调用的组件工具数量")
    tool_call_names: list[str] = Field(..., description="被调用的组件工具名称列表")
    tool_definition_tokens: int = Field(..., description="组件工具定义 token 数量")


class ResponseGenerationTokenStats(BaseTokenStats):
    """响应生成的 Token 统计"""

    reasoning_tokens: int | None = Field(None, description="推理内容 token 数量")
    content_tokens: int | None = Field(None, description="回答内容 token 数量")


class TitleGenerationTokenStats(BaseTokenStats):
    """标题生成的 Token 统计"""

    title: str | None = Field(None, description="生成的标题")


class CompressionTokenStats(BaseTokenStats):
    """上下文压缩的 Token 统计"""

    compression_ratio: float = Field(..., description="压缩比例")
    processing_time: float = Field(..., description="处理耗时（秒）")
    original_content_length: int | None = Field(None, description="原始内容长度")
    compressed_content_length: int | None = Field(None, description="压缩后内容长度")


class TotalTokenStats(BaseModel):
    """总 Token 统计（汇总所有阶段）"""

    mcp_tools: MCPToolsTokenStats | None = Field(None, description="MCP 工具调用统计")
    component_tools: ComponentToolsTokenStats | None = Field(
        None, description="组件工具调用统计"
    )
    response_generation: ResponseGenerationTokenStats | None = Field(
        None, description="响应生成统计"
    )
    title_generation: TitleGenerationTokenStats | None = Field(
        None, description="标题生成统计"
    )

    @property
    def total_prompt_tokens(self) -> int:
        """总输入 token 数量"""
        total = 0
        if self.mcp_tools:
            total += self.mcp_tools.token_usage.prompt_tokens
        if self.component_tools:
            total += self.component_tools.token_usage.prompt_tokens
        if self.response_generation:
            total += self.response_generation.token_usage.prompt_tokens
        if self.title_generation:
            total += self.title_generation.token_usage.prompt_tokens
        return total

    @property
    def total_completion_tokens(self) -> int:
        """总输出 token 数量"""
        total = 0
        if self.mcp_tools:
            total += self.mcp_tools.token_usage.completion_tokens
        if self.component_tools:
            total += self.component_tools.token_usage.completion_tokens
        if self.response_generation:
            total += self.response_generation.token_usage.completion_tokens
        if self.title_generation:
            total += self.title_generation.token_usage.completion_tokens
        return total

    @property
    def total_tokens(self) -> int:
        """总 token 数量"""
        return self.total_prompt_tokens + self.total_completion_tokens
