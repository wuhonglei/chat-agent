// Token 统计相关的类型定义

/**
 * Token 使用量统计
 */
export interface TokenUsage {
  promptTokens: number; // 输入 token 数量
  completionTokens: number; // 输出 token 数量
  totalTokens: number; // 总 token 数量
}

/**
 * Token 统计基类
 */
export interface BaseTokenStats {
  agentName: string; // Agent 名称
  modelName: string; // 使用的模型名称
  thinkMode: boolean; // 是否使用思考模式
  modelLimit: number; // 模型限制的 token 数量
  tokenUsage: TokenUsage; // Token 使用量
}

/**
 * MCP 工具调用的 Token 统计
 */
export interface MCPToolsTokenStats extends BaseTokenStats {
  toolCallCount: number; // 被调用的工具数量
  toolCallNames: string[]; // 被调用的工具名称列表
  toolDefinitionTokens: number; // 工具定义 token 数量
}

/**
 * 组件工具调用的 Token 统计
 */
export interface ComponentToolsTokenStats extends BaseTokenStats {
  toolCallCount: number; // 被调用的组件工具数量
  toolCallNames: string[]; // 被调用的组件工具名称列表
  toolDefinitionTokens: number; // 组件工具定义 token 数量
}

/**
 * 响应生成的 Token 统计
 */
export interface ResponseGenerationTokenStats extends BaseTokenStats {
  reasoningTokens?: number; // 推理内容 token 数量
  contentTokens?: number; // 回答内容 token 数量
}

/**
 * 标题生成的 Token 统计
 */
export interface TitleGenerationTokenStats extends BaseTokenStats {
  title?: string; // 生成的标题
}

/**
 * 总 Token 统计（汇总所有阶段）
 */
export interface TotalTokenStats {
  mcpTools?: MCPToolsTokenStats; // MCP 工具调用统计
  componentTools?: ComponentToolsTokenStats; // 组件工具调用统计
  responseGeneration?: ResponseGenerationTokenStats; // 响应生成统计
  titleGeneration?: TitleGenerationTokenStats; // 标题生成统计
}

/**
 * Token 统计类型（用于 ChatMessage 中的 tokenStats 字段）
 * 可能是 TotalTokenStats 或单个阶段的统计
 */
export type TokenStats =
  | TotalTokenStats
  | MCPToolsTokenStats
  | ComponentToolsTokenStats
  | ResponseGenerationTokenStats
  | TitleGenerationTokenStats;
