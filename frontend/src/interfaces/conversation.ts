import { TitleCreatedBy } from "@/constants";

// Conversation types
export interface ConversationInfo {
  id: string;
  title: string;
  createdBy: TitleCreatedBy;
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

export interface UpdateConversationRequest {
  id: string;
  title: string;
}

export interface ConversationDetailResponse extends ConversationInfo {}
