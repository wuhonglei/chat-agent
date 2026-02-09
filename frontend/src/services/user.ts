import { SendSmsResponse, UserInfo, UserProfileList, VerifySmsRequest, WeChatLoginInitResponse } from "@/interfaces";
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
  /** 查询用户画像列表（事实 + 偏好） */
  getMemories: async (): Promise<UserProfileList> => {
    return await apiClient.get("/user/memories");
  },
  /** 删除用户画像单条 */
  deleteMemory: async (itemId: string): Promise<void> => {
    return await apiClient.delete(`/user/memories/${itemId}`);
  },
};
