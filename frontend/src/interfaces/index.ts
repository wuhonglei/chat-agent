// Chat types
import { RoleType, SearchSourceType } from "@/constants";

export interface MCPConfigItem {
  id: string;
  name: string;
  icon: string;
  online: boolean;
  description: string;
}

export interface ChatMessage {
  role: RoleType;
  content: string;
  reasoning?: string;
  timestamp: string;
  sources?: SearchSource[];
  metadata: Omit<ChatInputFormValues, "message">;
}

export interface RetrieverSource {
  webSearch: boolean;
  confluence: boolean;
  googleDocs: boolean;
}

export interface ChatInputFormValues {
  message: string;
  thinkMode: boolean;
  sourceConfig: RetrieverSource;
}

export interface ChatRequest extends ChatInputFormValues {
  sessionId?: string;
  history?: ChatMessage[];
  stream?: boolean;
}

export interface ChatResponse {
  message: string;
  sources: SearchSource[];
  sessionId: string;
  timestamp: string;
}

export interface ChatSession {
  id: string;
  messages: ChatMessage[];
  createdAt: string;
  updatedAt: string;
  metadata?: Record<string, any>;
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
  metadata: SearchSourceMetaData;
}

// API types
export interface ApiResponse<T = any> {
  data: T;
  status: number;
  message?: string;
}

export interface ApiError {
  message: string;
  status?: number;
  detail?: string;
}

// Stream types
export interface StreamMessage {
  type: "reasoning" | "content" | "sources" | "done" | "error";
  data?: any;
}

// UI types
export interface Notification {
  id: string | number;
  type: "success" | "error" | "info" | "warning";
  message: string;
  description?: string;
  duration?: number;
}

export interface SourceData {
  index: number;
  sources: SearchSource[];
}
