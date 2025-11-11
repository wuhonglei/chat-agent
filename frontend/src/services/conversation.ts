import {
  ConversationInfo,
  ConversationListResponse,
  CreateConversationRequest,
  UpdateConversationRequest,
  ConversationDetailResponse,
} from "@/interfaces";
import { apiClient } from "./base";

// Conversation API
export const conversationAPI = {
  // 获取对话详情
  getConversation: async (
    conversationId: string
  ): Promise<ConversationDetailResponse> => {
    return await apiClient.get(`/api/conversation/detail/${conversationId}`);
  },

  // 创建对话
  createConversation: async (
    data?: CreateConversationRequest
  ): Promise<ConversationInfo> => {
    return await apiClient.post(
      "/api/conversation/register",
      data || { title: "新对话" }
    );
  },

  // 获取对话列表
  getConversations: async (params?: {
    limit?: number;
    offset?: number;
  }): Promise<ConversationListResponse> => {
    return await apiClient.get("/api/conversation/list", { params });
  },

  // 更新对话信息
  updateConversation: async (
    conversationId: string,
    data: UpdateConversationRequest
  ): Promise<ConversationInfo> => {
    return await apiClient.put(
      `/api/conversation/update/${conversationId}`,
      data
    );
  },

  // 删除对话
  deleteConversation: async (conversationId: string): Promise<string> => {
    return await apiClient.delete(`/api/conversation/delete/${conversationId}`);
  },
};
