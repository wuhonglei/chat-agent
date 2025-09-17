// Document types
export interface Document {
  id: string;
  name: string;
  source: DocumentSource;
  source_url?: string;
  content?: string;
  metadata?: Record<string, any>;
  status: DocumentStatus;
  created_at: string;
  updated_at: string;
  chunk_count: number;
}

export enum DocumentSource {
  LOCAL = "local",
  CONFLUENCE = "confluence",
  GOOGLE_DOCS = "google_docs",
  GOOGLE_SLIDES = "google_slides",
}

export enum DocumentStatus {
  PENDING = "pending",
  PROCESSING = "processing",
  COMPLETED = "completed",
  FAILED = "failed",
}

// Chat types
export interface ChatMessage {
  role: "user" | "assistant" | "system";
  content: string;
  reasoning?: string;
  timestamp: string;
  sources?: SearchSource[];
  metadata?: Record<string, any>;
}

export interface ChatInputFormValues {
  message: string;
  thinkMode: boolean;
  useKnowledgeBase: boolean;
  useNetwork: boolean;
}

export interface ChatRequest extends ChatInputFormValues {
  sessionId?: string;
  history?: ChatMessage[];
  stream?: boolean;
}

export interface ChatResponse {
  message: string;
  sources: SearchSource[];
  session_id: string;
  timestamp: string;
}

export interface ChatSession {
  id: string;
  messages: ChatMessage[];
  created_at: string;
  updated_at: string;
  metadata?: Record<string, any>;
}

// Search types
export interface SearchSource {
  content: string;
  document_name: string;
  document_id?: string;
  score: number;
  metadata?: Record<string, any>;
  source_url?: string;
}

// Knowledge base types
export interface KnowledgeBaseStats {
  document_count: number;
  total_chunks: number;
  sources: {
    local: number;
    confluence: number;
    google_docs: number;
    google_slides: number;
  };
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
