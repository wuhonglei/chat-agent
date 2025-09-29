import { fetchEventSource } from "@microsoft/fetch-event-source";
import { AxiosResponse } from "axios";

import {
  ChatRequest,
  ChatResponse,
  ChatSession,
  StreamMessage,
} from "@/interfaces";
import { apiClient } from "./base";
import snakecaseKeys from "snakecase-keys";
import camelcaseKeys from "camelcase-keys";

// Chat API
export const chatAPI = {
  // Send message
  sendMessage: async (
    data: ChatRequest
  ): Promise<AxiosResponse<ChatResponse>> => {
    return await apiClient.post("/api/chat", data);
  },

  // Stream message
  streamMessage: async (
    data: ChatRequest,
    onMessage: (message: StreamMessage) => void,
    onError: (error: Error) => void,
    onClose: () => void,
    abortController: AbortController
  ): Promise<void> => {
    await fetchEventSource(`${apiClient.defaults.baseURL}/api/chat/stream`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(
        snakecaseKeys(data as unknown as Record<string, unknown>, {
          deep: true,
        })
      ),
      signal: abortController.signal,
      onmessage(event) {
        if (event.data) {
          try {
            const parsed: StreamMessage = camelcaseKeys(
              JSON.parse(event.data),
              { deep: true }
            );
            onMessage(parsed);
          } catch (e) {
            console.error("Failed to parse message:", e);
          }
        }
      },
      onerror(err) {
        onError(err as Error);
        throw err;
      },
      onclose() {
        onClose();
      },
      openWhenHidden: true,
    });

    return;
  },

  // Get session history
  getSession: async (
    sessionId: string
  ): Promise<AxiosResponse<ChatSession>> => {
    return await apiClient.get(`/api/chat/sessions/${sessionId}`);
  },

  // Delete session
  deleteSession: async (sessionId: string): Promise<AxiosResponse> => {
    return await apiClient.delete(`/api/chat/sessions/${sessionId}`);
  },
};

// Health Check API
export const healthAPI = {
  // Health check
  checkHealth: async (): Promise<AxiosResponse<{ status: string }>> => {
    return await apiClient.get("/api/health");
  },

  // Ready check
  checkReady: async (): Promise<AxiosResponse<{ status: string }>> => {
    return await apiClient.get("/api/health/ready");
  },
};
