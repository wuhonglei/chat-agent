import { fetchEventSource } from "@microsoft/fetch-event-source";
import axios, {
  AxiosInstance,
  AxiosResponse,
  InternalAxiosRequestConfig,
} from "axios";

import {
  ChatRequest,
  ChatResponse,
  ChatSession,
  StreamMessage,
} from "@/interfaces";
import { isPlainObject } from "lodash-es";
import snakecaseKeys from "snakecase-keys";
import camelcaseKeys from "camelcase-keys";

// Create axios instance
const apiClient: AxiosInstance = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "http://localhost:8000",
  timeout: 60000,
  headers: {
    "Content-Type": "application/json",
  },
});

// Request interceptor - Convert all request data to snake_case
apiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    // Convert request data to snake_case
    if (isPlainObject(config.data) && !(config.data instanceof FormData)) {
      config.data = snakecaseKeys(config.data, { deep: true });
    }
    // Convert params to snake_case
    if (isPlainObject(config.params)) {
      config.params = snakecaseKeys(config.params, { deep: true });
    }
    // Add token or other auth headers here if needed
    return config;
  },
  error => {
    return Promise.reject(error);
  }
);

// Response interceptor - Convert all response data to camelCase
apiClient.interceptors.response.use(
  (response: AxiosResponse) => {
    // Convert response data to camelCase
    if (isPlainObject(response.data) && !(response.data instanceof Blob)) {
      response.data = camelcaseKeys(response.data, { deep: true });
    }
    return response;
  },
  error => {
    if (error.response) {
      // Convert error response to camelCase
      if (isPlainObject(error.response.data)) {
        error.response.data = camelcaseKeys(error.response.data, {
          deep: true,
        });
      }
      console.error("API Error:", error.response.data);
    } else if (error.request) {
      console.error("Network Error:", error.request);
    } else {
      console.error("Error:", error.message);
    }
    return Promise.reject(error);
  }
);

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

export default apiClient;
