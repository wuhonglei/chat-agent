import axios, {
  AxiosInstance,
  InternalAxiosRequestConfig,
  AxiosResponse,
} from "axios";
import { fetchEventSource } from "@microsoft/fetch-event-source";
import {
  ChatRequest,
  ChatResponse,
  ChatSession,
  Document,
  DocumentSource,
  KnowledgeBaseStats,
  StreamMessage,
} from "../types";

// Create axios instance
const apiClient: AxiosInstance = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "http://localhost:8000",
  timeout: 60000,
  headers: {
    "Content-Type": "application/json",
  },
});

// Request interceptor
apiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    // Add token or other auth headers here if needed
    return config;
  },
  (error) => {
    return Promise.reject(error);
  },
);

// Response interceptor
apiClient.interceptors.response.use(
  (response: AxiosResponse) => {
    return response;
  },
  (error) => {
    if (error.response) {
      console.error("API Error:", error.response.data);
    } else if (error.request) {
      console.error("Network Error:", error.request);
    } else {
      console.error("Error:", error.message);
    }
    return Promise.reject(error);
  },
);

// Chat API
export const chatAPI = {
  // Send message
  sendMessage: async (
    data: ChatRequest,
  ): Promise<AxiosResponse<ChatResponse>> => {
    return await apiClient.post("/api/chat", data);
  },

  // Stream message
  streamMessage: async (
    data: ChatRequest,
    onMessage: (message: StreamMessage) => void,
    onError: (error: Error) => void,
    onClose: () => void,
  ): Promise<AbortController> => {
    const ctrl = new AbortController();

    await fetchEventSource(`${apiClient.defaults.baseURL}/api/chat/stream`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(data),
      signal: ctrl.signal,
      onmessage(event) {
        if (event.data) {
          try {
            const parsed: StreamMessage = JSON.parse(event.data);
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
    });

    return ctrl;
  },

  // Get session history
  getSession: async (
    sessionId: string,
  ): Promise<AxiosResponse<ChatSession>> => {
    return await apiClient.get(`/api/chat/sessions/${sessionId}`);
  },

  // Delete session
  deleteSession: async (sessionId: string): Promise<AxiosResponse> => {
    return await apiClient.delete(`/api/chat/sessions/${sessionId}`);
  },
};

// Document API
export const documentAPI = {
  // Get documents list
  getDocuments: async (): Promise<AxiosResponse<Document[]>> => {
    return await apiClient.get("/api/documents");
  },

  // Upload document
  uploadDocument: async (
    formData: FormData,
    onUploadProgress?: (progressEvent: any) => void,
  ): Promise<AxiosResponse<Document>> => {
    return await apiClient.post("/api/documents/upload", formData, {
      headers: {
        "Content-Type": "multipart/form-data",
      },
      onUploadProgress,
    });
  },

  // Import from URL
  importFromUrl: async (
    url: string,
    source: DocumentSource,
  ): Promise<AxiosResponse<Document>> => {
    return await apiClient.post("/api/documents/import-url", null, {
      params: { url, source },
    });
  },

  // Delete document
  deleteDocument: async (documentId: string): Promise<AxiosResponse> => {
    return await apiClient.delete(`/api/documents/${documentId}`);
  },
};

// Knowledge Base API
export const knowledgeBaseAPI = {
  // Export knowledge base
  exportKnowledgeBase: async (): Promise<AxiosResponse<Blob>> => {
    return await apiClient.get("/api/knowledge-base/export", {
      responseType: "blob",
    });
  },

  // Import knowledge base
  importKnowledgeBase: async (file: File): Promise<AxiosResponse> => {
    const formData = new FormData();
    formData.append("file", file);
    return await apiClient.post("/api/knowledge-base/import", formData, {
      headers: {
        "Content-Type": "multipart/form-data",
      },
    });
  },

  // Create share link
  createShareLink: async (): Promise<AxiosResponse<{ link: string }>> => {
    return await apiClient.get("/api/knowledge-base/share");
  },

  // Get statistics
  getStats: async (): Promise<AxiosResponse<KnowledgeBaseStats>> => {
    return await apiClient.get("/api/knowledge-base/stats");
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
