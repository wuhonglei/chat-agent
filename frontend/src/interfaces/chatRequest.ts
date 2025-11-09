// Chat types
import { RoleType, SearchSourceType, TitleCreatedBy } from "@/constants";
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
  id?: string;
  role: RoleType;
  content: string;
  reasoning?: string;
  createdAt: string;
  sources?: SearchSource[];
  toolCalls?: ToolCallMessage[];
  messageMetadata: Omit<ChatInputFormValues, "message">;
  status?: "pending" | "done" | "failed";
  replyTo?: string; // role为assistant时，回复到哪个user消息
}

export interface ChatHistory {
  role: RoleType;
  content: string;
}

export interface ChatResponse {
  message: string;
  sources: SearchSource[];
  created_at: string;
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
  history: ChatHistory[];
  regenerateTitle: boolean;
}

export interface SourceData {
  index: number;
  sources: SearchSource[];
}

export interface SendMessageOptions {
  index?: number;
  createdBy?: TitleCreatedBy;
  conversationIdOverride?: string;
}
