import {
  SendSmsResponse,
  UserInfo,
  VerifySmsRequest,
  WeChatLoginCheckResponse,
  WeChatLoginInitResponse,
} from "@/interfaces";
import { apiClient } from "./base";

export const userAPI = {
  getUserDetail: async (): Promise<UserInfo> => {
    return await apiClient.get("/user/detail");
  },
  sendVerificationCode: async (
    phoneNumber: string
  ): Promise<SendSmsResponse> => {
    return await apiClient.post("/auth/send_sms", { phoneNumber });
  },
  loginWithVerificationCode: async (
    data: VerifySmsRequest
  ): Promise<UserInfo> => {
    return await apiClient.post("/auth/verify_sms", data);
  },
  logout: async (): Promise<void> => {
    return await apiClient.post("/auth/logout");
  },
  updateUserInfo: async (data: Partial<UserInfo>): Promise<UserInfo> => {
    return await apiClient.put("/user/update_info", data);
  },
  initWeChatLogin: async (
    oldState?: string
  ): Promise<WeChatLoginInitResponse> => {
    return await apiClient.post("/auth/wechat/init", { oldState });
  },
  checkWeChatLoginStatus: async (
    state: string
  ): Promise<WeChatLoginCheckResponse> => {
    return await apiClient.post("/auth/wechat/check", { state });
  },
};
