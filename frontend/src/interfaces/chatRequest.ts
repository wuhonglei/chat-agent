// Chat types
import { RoleType, SearchSourceType } from "@/constants";
import { ToolCallMessage } from "./tooCall";

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
  role: RoleType;
  content: string;
  reasoning?: string;
  timestamp: string;
  sources?: SearchSource[];
  toolCalls?: ToolCallMessage[];
  messageMetadata: Omit<ChatInputFormValues, "message">;
}

export interface ChatResponse {
  message: string;
  sources: SearchSource[];
  timestamp: string;
}

export interface RetrieverSource {
  [key: string]: boolean;
}

export interface ChatInputFormValues {
  message: string;
  thinkMode: boolean;
  mcpAutoMode: boolean;
  sourceConfig: RetrieverSource;
}

export interface ChatRequest extends ChatInputFormValues {
  conversationId?: string;
  history?: ChatMessage[];
  stream?: boolean;
}

export interface SourceData {
  index: number;
  sources: SearchSource[];
}
