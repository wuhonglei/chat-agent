import {
  ConversationInfo,
  ConversationDetailResponse,
  ConversationListResponse,
  CreateConversationRequest,
  UpdateConversationRequest,
} from "@/interfaces";
import { apiClient } from "./base";

// Conversation API
export const conversationAPI = {
  // 创建对话
  createConversation: async (
    data?: CreateConversationRequest
  ): Promise<ConversationInfo> => {
    return await apiClient.post("/api/conversations", data || {});
  },

  // 获取对话详情
  getConversation: async (
    conversationId: string
  ): Promise<ConversationDetailResponse> => {
    return await apiClient.get(`/api/conversations/${conversationId}`);
  },

  // 获取对话列表
  getConversations: async (params?: {
    limit?: number;
    offset?: number;
  }): Promise<ConversationListResponse> => {
    return await apiClient.get("/api/conversations", { params });
  },

  // 更新对话信息
  updateConversation: async (
    conversationId: string,
    data: UpdateConversationRequest
  ): Promise<ConversationInfo> => {
    return await apiClient.put(`/api/conversations/${conversationId}`, data);
  },

  // 删除对话
  deleteConversation: async (conversationId: string): Promise<string> => {
    return await apiClient.delete(`/api/conversations/${conversationId}`);
  },
};
