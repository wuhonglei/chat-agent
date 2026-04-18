import {
  ConversationDetailResponse,
  ConversationInfo,
  ConversationListResponse,
  CreateConversationRequest,
  UpdateConversationRequest,
} from "@/interfaces";
import { withDevConversationTitlePrefix } from "@/utils/common";
import { apiClient } from "./base";

// Conversation API
export const conversationAPI = {
  // 获取对话详情
  getConversation: async (conversationId: string): Promise<ConversationDetailResponse> => {
    return await apiClient.get(`/conversation/detail/${conversationId}`);
  },

  // 创建对话
  createConversation: async (data?: CreateConversationRequest): Promise<ConversationInfo> => {
    const base = data ?? { title: withDevConversationTitlePrefix("新对话") };
    return await apiClient.post("/conversation/register", base);
  },

  // 获取对话列表
  getConversations: async (params?: { limit?: number; offset?: number }): Promise<ConversationListResponse> => {
    return await apiClient.get("/conversation/list", { params });
  },

  // 更新对话信息
  updateConversation: async (conversationId: string, data: UpdateConversationRequest): Promise<ConversationInfo> => {
    return await apiClient.put(`/conversation/update/${conversationId}`, data);
  },

  // 删除对话
  deleteConversation: async (conversationId: string): Promise<string> => {
    return await apiClient.delete(`/conversation/delete/${conversationId}`);
  },
};
