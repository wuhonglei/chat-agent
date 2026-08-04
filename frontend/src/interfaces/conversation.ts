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
  conversations: ConversationInfo[];
  nextCursor: string | null;
  hasMore: boolean;
  limit: number;
}

export interface UpdateConversationRequest {
  id: string;
  title: string;
  createdBy: TitleCreatedBy;
}

export type ConversationDetailResponse = ConversationInfo;

export type ConversationSearchMatchType = "title" | "user" | "assistant";

export interface ConversationSearchItem {
  id: string;
  title: string;
  matchType: ConversationSearchMatchType;
  snippet: string;
  updatedAt: string;
}

export interface ConversationSearchResponse {
  conversations: ConversationSearchItem[];
  nextCursor: string | null;
  hasMore: boolean;
  limit: number;
}
