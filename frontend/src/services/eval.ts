import {
  BadCaseItem,
  BadCaseListParams,
  BadCaseListResponse,
  BadCaseStatsResponse,
  BadCaseUpdateRequest,
} from "@/interfaces/eval";
import { apiClient } from "./base";

export const evalAPI = {
  listBadCases: async (params?: BadCaseListParams): Promise<BadCaseListResponse> => {
    return await apiClient.get("/eval/bad-cases", { params });
  },

  getBadCaseStats: async (): Promise<BadCaseStatsResponse> => {
    return await apiClient.get("/eval/bad-cases/stats");
  },

  getBadCase: async (itemId: string): Promise<BadCaseItem> => {
    return await apiClient.get(`/eval/bad-cases/${itemId}`);
  },

  updateBadCase: async (itemId: string, data: BadCaseUpdateRequest): Promise<BadCaseItem> => {
    return await apiClient.put(`/eval/bad-cases/${itemId}`, data);
  },

  addToDataset: async (itemId: string): Promise<BadCaseItem> => {
    return await apiClient.post(`/eval/bad-cases/${itemId}/add-to-dataset`);
  },
};
