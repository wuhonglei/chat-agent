import { TitleCreatedBy } from "@/constants";
import { ChatMessage } from "./chatRequest";

// Conversation types
export interface ConversationInfo {
  id: string;
  title: string;
  createdAt: string;
  updatedAt: string;
  messageCount: number;
  createdBy: TitleCreatedBy;
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

export interface UpdateConversationRequest {
  id: string;
  title: string;
}

export interface ConversationDetailResponse extends ConversationInfo {}

export interface ConversationMessageListResponse {
  total: number;
  offset: number;
  limit: number;
  messages: ChatMessage[];
}
