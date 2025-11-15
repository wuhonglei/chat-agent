import { fetchEventSource } from "@microsoft/fetch-event-source";
import { AxiosResponse } from "axios";

import {
  ChatRequest,
  StreamMessage,
  MCPConfigItem,
  ChatMessage,
} from "@/interfaces";
import { apiClient } from "./base";
import snakecaseKeys from "snakecase-keys";
import camelcaseKeys from "camelcase-keys";

// Chat API
export const chatAPI = {
  // 获取对话消息列表
  getConversationMessages: async (
    conversationId: string
  ): Promise<ChatMessage[]> => {
    const res = await apiClient.get(`/conversation/${conversationId}/messages`);
    // @ts-expect-error - TODO: fix this
    return res.messages;
  },

  deleteMessage: async (messageId: string): Promise<void> => {
    await apiClient.delete(`/message/delete/${messageId}`);
  },

  // Stream message
  streamMessage: async (
    data: ChatRequest,
    onMessage: (message: StreamMessage) => void,
    onError: (error: Error) => void,
    onClose: () => void,
    abortController: AbortController
  ): Promise<void> => {
    await fetchEventSource(`${apiClient.defaults.baseURL}/chat/stream`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(
        snakecaseKeys(data as unknown as Record<string, unknown>, {
          deep: true,
          // 不修改服务端返回的 mcp server id
          exclude: Object.keys(data.sourceConfig || {}),
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
};

// Health Check API
export const healthAPI = {
  // Health check
  checkHealth: async (): Promise<AxiosResponse<{ status: string }>> => {
    return await apiClient.get("/health");
  },

  // MCP health check
  checkMCPHealth: async (): Promise<AxiosResponse<{ status: string }>> => {
    return await apiClient.get("/health/mcp");
  },

  // MCP config
  getMCPConfig: async (): Promise<MCPConfigItem[]> => {
    return await apiClient.get("/health/mcp_config");
  },
};
