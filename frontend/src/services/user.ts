import { MemoryListItem, MemoryListParams, MemoryListResponse, SendSmsResponse, UserInfo, VerifySmsRequest, WeChatLoginInitResponse } from "@/interfaces";
import { apiClient } from "./base";

export const userAPI = {
  getUserDetail: async (): Promise<UserInfo> => {
    return await apiClient.get("/user/detail");
  },
  sendVerificationCode: async (phoneNumber: string): Promise<SendSmsResponse> => {
    return await apiClient.post("/auth/sms/send", { phoneNumber });
  },
  loginWithVerificationCode: async (data: VerifySmsRequest): Promise<UserInfo> => {
    return await apiClient.post("/auth/sms/login", data);
  },
  logout: async (): Promise<void> => {
    return await apiClient.post("/auth/logout");
  },
  updateUserInfo: async (data: Partial<UserInfo>): Promise<UserInfo> => {
    return await apiClient.put("/user/update_info", data);
  },
  initWeChatLogin: async (oldState?: string): Promise<WeChatLoginInitResponse> => {
    return await apiClient.post("/auth/wechat/init", { oldState });
  },
  weChatLoginCallback: async (data: { code: string; state: string }): Promise<UserInfo> => {
    return await apiClient.post("/auth/wechat/login", data);
  },
};

export const profileAPI = {
  /** 查询用户记忆列表 */
  getMemories: async (params?: MemoryListParams): Promise<MemoryListResponse> => {
    return await apiClient.get("/user/memories", { params });
  },
  /** 按 query 搜索用户记忆 */
  searchMemories: async (q: string): Promise<MemoryListResponse> => {
    return await apiClient.get("/user/memories/search", { params: { q } });
  },
  /** 按 id 查询单条用户记忆 */
  getMemory: async (itemId: string): Promise<MemoryListItem> => {
    return await apiClient.get(`/user/memories/${itemId}`);
  },
  /** 删除单条用户记忆 */
  deleteMemory: async (itemId: string): Promise<void> => {
    return await apiClient.delete(`/user/memories/${itemId}`);
  },
};
