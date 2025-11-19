import { apiClient } from "./base";
import { UserInfo } from "@/interfaces";

export const UserAPI = {
  getUserDetail: async (): Promise<UserInfo> => {
    return await apiClient.get("/user/detail");
  },
};
