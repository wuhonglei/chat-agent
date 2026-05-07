// Chat types
import { ContentBlock, UserAttachmentBlock, UserContentBlock } from "./contentBlock";
import { TitleCreatedBy } from "./conversation";

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

export type MessageFeedbackValue = "default" | "like" | "dislike";

export interface MessageFeedback {
  value: MessageFeedbackValue;
  updatedAt: string;
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
  contentBlocks: ContentBlock[];
  createdAt: string;
  updatedAt: string;
  status: MessageStatus;
  messageMetadata: Omit<ChatInputFormValues, "message">;
  replyTo: string; // role为assistant时，回复到哪个user消息
  feedback?: MessageFeedback;
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
  modelName: string;
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
      /** 欢迎页等场景下与 values 一并缓存，供跳转后首条消息使用（可 JSON 序列化） */
      attachmentBlocks?: UserAttachmentBlock[];
      createdBy: TitleCreatedBy;
      insertAt: number; // 时间戳 ms (Date.now() 生成)
    };

export interface ChatRequest extends ChatInputConfig {
  contentBlocks: UserContentBlock[];
  conversationId?: string;
  historyIds: string[];
  regenerateTitle: boolean;
  removedMessageIds: string[];
}

export interface ChatModelItem {
  id: string;
  modelName: string;
  imageSupport: boolean;
}

export interface SourceData {
  index: number;
  sources: SearchSource[];
}

export interface SendMessageOptions {
  index?: number;
  createdBy?: TitleCreatedBy;
  /** 与 Attachments 派生并列：重发时从历史消息的 contentBlocks 带入（图片、PDF 等） */
  attachmentBlocks?: UserAttachmentBlock[];
}

export type StreamResumePhase = "streaming" | "closed" | "done" | "error";

export interface StreamResumeContext {
  assistantMessageId: string;
  lastSeq: number;
  phase: StreamResumePhase;
  updatedAt: string;
}

export interface ChatConversationState {
  messages: ChatMessage[];
  messageLoaded: boolean;
  lastMessageUpdateAt: string; // 等价于 messages.at(-1).createdAt
  isLoading: boolean;
  isStreaming: boolean;
  streamResumeContext: StreamResumeContext | null;
}
