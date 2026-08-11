import {
  BadCaseItem,
  BadCaseListParams,
  BadCaseListResponse,
  BadCaseStatsResponse,
  BadCaseUpdateRequest,
  EvalRunLog,
  EvalRunLogListParams,
  EvalRunLogListResponse,
  EvalRunTriggerRequest,
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

  deleteBadCase: async (itemId: string): Promise<void> => {
    await apiClient.delete(`/eval/bad-cases/${itemId}`);
  },

  addToDataset: async (itemId: string): Promise<BadCaseItem> => {
    return await apiClient.post(`/eval/bad-cases/${itemId}/add-to-dataset`);
  },

  listRunLogs: async (params?: EvalRunLogListParams): Promise<EvalRunLogListResponse> => {
    return await apiClient.get("/eval/run-logs", { params });
  },

  getRunLog: async (runId: string): Promise<EvalRunLog> => {
    return await apiClient.get(`/eval/run-logs/${runId}`);
  },

  deleteRunLog: async (runId: string): Promise<void> => {
    await apiClient.delete(`/eval/run-logs/${runId}`);
  },

  triggerBatchEval: async (data?: EvalRunTriggerRequest): Promise<EvalRunLog> => {
    return await apiClient.post("/eval/run-logs/trigger", data ?? {});
  },
};
