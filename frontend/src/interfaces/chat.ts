// Chat types
import {
  MessageStatus,
  RoleType,
  SearchSourceType,
  TitleCreatedBy,
} from "@/constants";
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
  id: string;
  role: RoleType;
  content: string;
  reasoning: string;
  createdAt: string;
  sources: SearchSource[];
  toolCalls: ToolCallMessage[];
  messageMetadata: Omit<ChatInputFormValues, "message">;
  status: MessageStatus;
  replyTo: string; // role为assistant时，回复到哪个user消息
  defaultOpen?: boolean; // 默认展开(思考内容、工具调用、来源)
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
}

export interface SourceData {
  index: number;
  sources: SearchSource[];
}

export interface SendMessageOptions {
  index?: number;
  createdBy?: TitleCreatedBy;
}
