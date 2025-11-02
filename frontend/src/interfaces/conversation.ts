import { ChatMessage } from "./chatRequest";

// Conversation types
export interface ConversationInfo {
  id: string;
  title: string;
  createdAt: string;
  updatedAt: string;
  messageCount: number;
}

export interface CreateConversationRequest {
  title?: string;
}

export interface ConversationListResponse {
  total: number;
  offset: number;
  limit: number;
  conversations: ConversationInfo[];
}

export interface ConversationDetailResponse extends ConversationInfo {
  messages: ChatMessage[];
}

export interface UpdateConversationRequest {
  id: string;
  title: string;
}
