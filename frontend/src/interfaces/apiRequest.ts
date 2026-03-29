import { ChatMessage } from "./chat";
import { ConversationInfo } from "./conversation";
import { TotalTokenStats } from "./token";
import { ToolCallMessage } from "./tooCall";

// Stream types
export type StreamMessage =
  | {
      type: "ack";
      data: ChatMessage;
    }
  | {
      type: "refresh_conversation";
      data: ConversationInfo;
    }
  | {
      type: "reasoning";
      data: {
        status?: "start" | "done";
        content?: string;
      };
    }
  | {
      type: "content";
      data: {
        content?: string;
      };
    }
  | {
      type: "mcp_tool_call";
      data: ToolCallMessage;
    }
  | {
      type: "title";
      data: {
        id: string;
        title: string;
      };
    }
  | {
      type: "done";
      data: {
        userMessageId: string;
        conversationId: string;
        assistantMessageId: string;
        lastMessageUpdatedAt: string;
        contentLength: number;
        reasoningLength: number;
        toolCallsLength: number;
        tokenStats?: TotalTokenStats; // 后端 token_stats 转小驼峰
      };
    }
  | {
      type: "error";
      data: {
        content: string; // 错误信息
      };
    };

export type StreamMessageHandlerMap = {
  [type in StreamMessage["type"]]: (data: Extract<StreamMessage, { type: type }>["data"]) => void;
};
