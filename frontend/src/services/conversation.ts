import {
  ConversationDetailResponse,
  ConversationInfo,
  ConversationListResponse,
  ConversationSearchResponse,
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
  registerConversation: async (data?: CreateConversationRequest): Promise<ConversationInfo> => {
    const base = data ?? { title: withDevConversationTitlePrefix("新对话") };
    return await apiClient.post("/conversation/register", base);
  },

  activateConversation: async (conversationId: string): Promise<ConversationInfo> => {
    return await apiClient.put(`/conversation/activate/${conversationId}`);
  },

  // 获取对话列表（游标分页）
  getConversations: async (params?: {
    limit?: number;
    cursor?: string | null;
  }): Promise<ConversationListResponse> => {
    return await apiClient.get("/conversation/list", { params });
  },

  // 搜索对话（标题 + 消息正文）
  searchConversations: async (params: {
    q: string;
    limit?: number;
    cursor?: string | null;
  }): Promise<ConversationSearchResponse> => {
    return await apiClient.get("/conversation/search", { params });
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
