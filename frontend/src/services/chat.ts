import { fetchEventSource } from "@microsoft/fetch-event-source";
import { AxiosResponse } from "axios";

import { authHeader } from "@/constants";
import {
  ChatMessage,
  ChatRequest,
  MCPConfigItem,
  MessageFeedback,
  MessageFeedbackValue,
  StreamMessage,
} from "@/interfaces";
import { isUnAuthorized, reportError, toLoginPage } from "@/utils";
import camelcaseKeys from "camelcase-keys";
import snakecaseKeys from "snakecase-keys";
import { addRequestHeaders, apiClient } from "./base";

// Chat API
export const chatAPI = {
  // 获取对话消息列表
  getConversationMessages: async (conversationId: string): Promise<ChatMessage[]> => {
    const res = await apiClient.get(`/conversation/${conversationId}/messages`);
    // @ts-expect-error - TODO: fix this
    return res.messages;
  },

  deleteMessage: async (messageId: string): Promise<void> => {
    await apiClient.delete(`/message/delete/${messageId}`);
  },

  updateMessageFeedback: async (messageId: string, value: MessageFeedbackValue): Promise<MessageFeedback> => {
    return await apiClient.put(`/message/feedback/${messageId}`, { value });
  },

  // Stream message
  streamMessage: async (
    data: ChatRequest,
    onMessage: (message: StreamMessage) => void,
    onError: (error: Error) => void,
    onClose: () => void,
    abortController: AbortController
  ): Promise<void> => {
    const body = JSON.stringify(
      snakecaseKeys(data as unknown as Record<string, unknown>, {
        deep: true,
        // 不修改服务端返回的 mcp server id
        exclude: Object.keys(data.sourceConfig || {}),
      })
    );
    await fetchEventSource(`${apiClient.defaults.baseURL}/chat/stream`, {
      method: "POST",
      headers: addRequestHeaders({
        "Content-Type": "application/json",
      }),
      body,
      signal: abortController.signal,
      onopen: async (response: Response): Promise<void> => {
        // 如果响应状态码为 401，则跳转至登录页面
        if (isUnAuthorized(response.status)) {
          reportError("Stream Unauthorized Error", {
            status: response.status,
            url: `${apiClient.defaults.baseURL}/chat/stream`,
            method: "POST",
          });
          authHeader.removeAuthorizationHeader();
          toLoginPage(location.pathname);
          return Promise.reject(new Error("Unauthorized"));
        }
      },
      onmessage(event) {
        if (event.data) {
          try {
            const parsed: StreamMessage = camelcaseKeys(JSON.parse(event.data), { deep: true });
            onMessage(parsed);
          } catch (e) {
            // 上报消息解析错误
            reportError("Stream Parse Error", {
              error: e instanceof Error ? e.message : String(e),
              data: event.data.substring(0, 200), // 只上报前200个字符，避免数据过大
            });
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
