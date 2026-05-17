// Conversation types
export enum TitleCreatedBy {
  Default = "default",
  User = "user",
  LLM = "llm",
}

export interface ConversationInfo {
  id: string;
  title: string;
  createdBy: TitleCreatedBy;
  isActive?: boolean;
  updatedAt: string;
  lastMessageCreatedAt: string;
  lastMessageUpdatedAt: string;
}

export interface EditConversationInfo {
  id: string;
  title: string;
}

export interface CreateConversationRequest {
  title?: string;
  isActive?: boolean;
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
  createdBy: TitleCreatedBy;
}

export type ConversationDetailResponse = ConversationInfo;
