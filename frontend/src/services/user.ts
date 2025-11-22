import { apiClient } from "./base";
import { UserInfo } from "@/interfaces";
import { SendSmsResponse, VerifySmsRequest } from "@/interfaces";

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
};
