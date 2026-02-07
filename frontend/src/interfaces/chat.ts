// Chat types
import { ComponentToolRequestItem } from "./componentTools";
import { TitleCreatedBy } from "./conversation";
import { TotalTokenStats } from "./token";
import { ToolCallMessage } from "./tooCall";

export enum SearchSourceType {
  WebSearch = "web_search",
  Confluence = "confluence",
}

export type RoleType = "user" | "assistant" | "system";

export enum MessageStatus {
  Pending = "pending",
  Stopped = "stopped",
  Done = "done",
  Failed = "failed",
}

export interface SearchSourceMetaData {
  lastModifiedTime?: string; // "2025-09-26T15:48:43.000+08:00";
  lastModifierName?: string; // "张三";
  spaceKey?: string;
  spaceName?: string;
}

// Search types
export interface SearchSource {
  content: string;
  title: string;
  score: number;
  url?: string;
  favicon?: string;
  source: SearchSourceType;
  messageMetadata: SearchSourceMetaData;
}

export interface ChatMessage {
  id: string;
  role: RoleType;
  content: string;
  reasoning: string;
  createdAt: string;
  updatedAt: string;
  toolCallsDuration: number;
  componentToolCallsDuration: number;
  reasoningDuration: number;
  contentDuration: number;
  totalDuration: number;
  toolCalls: ToolCallMessage[];
  componentToolCalls: ToolCallMessage[];
  status: MessageStatus;
  messageMetadata: Omit<ChatInputFormValues, "message">;
  replyTo: string; // role为assistant时，回复到哪个user消息
  tokenStats: TotalTokenStats;
}

export interface ChatHistory {
  role: RoleType;
  content: string;
}

export interface RetrieverSource {
  [key: string]: boolean;
}

export interface ChatInputConfig {
  thinkMode: boolean;
  mcpAutoMode: boolean;
  sourceConfig: RetrieverSource;
}

export interface ChatInputFormValues extends ChatInputConfig {
  content: string;
}

export type NewConversationCache =
  | {
      isNewConversation: false;
      values?: ChatInputFormValues;
      createdBy?: TitleCreatedBy;
      insertAt?: number; // 时间戳 ms (Date.now() 生成)
    }
  | {
      isNewConversation: true;
      values: ChatInputFormValues;
      createdBy: TitleCreatedBy;
      insertAt: number; // 时间戳 ms (Date.now() 生成)
    };

export interface ChatRequest extends ChatInputFormValues {
  conversationId?: string;
  historyIds: string[];
  regenerateTitle: boolean;
  removedMessageIds: string[];
  componentToolsForBackend: Pick<ComponentToolRequestItem, "name" | "whenCondition" | "when">[];
}

export interface SourceData {
  index: number;
  sources: SearchSource[];
}

export interface SendMessageOptions {
  index?: number;
  createdBy?: TitleCreatedBy;
}

export interface ChatConversationState {
  messages: ChatMessage[];
  messageLoaded: boolean;
  lastMessageUpdateAt: string; // 等价于 messages.at(-1).createdAt
  isLoading: boolean;
  isStreaming: boolean;
  isReasoning: boolean;
  isCallingMcpTools: boolean;
  isCallingComponentTools: boolean;
}
