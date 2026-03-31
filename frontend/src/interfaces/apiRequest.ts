import { ChatMessage } from "./chat";
import { ContentBlockEvent } from "./contentBlock";
import { ConversationInfo } from "./conversation";

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
      type: "title";
      data: {
        id: string;
        title: string;
      };
    }
  | {
      type: "content_block";
      data: ContentBlockEvent;
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
