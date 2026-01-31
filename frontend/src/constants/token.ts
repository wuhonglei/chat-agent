export enum TokenStatsAgentName {
  TitleGeneration = "title_generation",
  McpTools = "mcp_tools",
  ComponentTools = "component_tools",
  ResponseGeneration = "response_generation",
}

export const TOKEN_STATS_TITLE_BY_AGENT_NAME = {
  [TokenStatsAgentName.TitleGeneration]: "标题生成",
  [TokenStatsAgentName.McpTools]: "MCP 工具调用",
  [TokenStatsAgentName.ComponentTools]: "组件工具调用",
  [TokenStatsAgentName.ResponseGeneration]: "响应生成",
} as const;

export const TOKEN_STATS_AGENT_NAMES_SORTED = [
  TokenStatsAgentName.TitleGeneration,
  TokenStatsAgentName.McpTools,
  TokenStatsAgentName.ComponentTools,
  TokenStatsAgentName.ResponseGeneration,
] as const;
