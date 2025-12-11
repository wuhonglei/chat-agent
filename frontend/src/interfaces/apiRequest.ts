import { ChatMessage } from "./chat";
import { ConversationInfo } from "./conversation";
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
        duration?: number;
      };
    }
  | {
      type: "content";
      data: {
        content?: string;
      };
    }
  | {
      type: "tool_call";
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
        toolCallsDuration: number;
        reasoningDuration: number;
        contentDuration: number;
        totalDuration: number;
      };
    }
  | {
      type: "error";
      data: {
        msg?: string;
        code?: number;
        details?: unknown;
      };
    };

export type StreamMessageHandlerMap = {
  [type in StreamMessage["type"]]: (
    data: Extract<StreamMessage, { type: type }>["data"]
  ) => void;
};
