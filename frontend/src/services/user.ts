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
  verifyVerificationCode: async (data: VerifySmsRequest): Promise<UserInfo> => {
    return await apiClient.post("/auth/verify_sms", data);
  },
};
