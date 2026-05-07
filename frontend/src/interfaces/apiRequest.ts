import { ChatMessage } from "./chat";
import { ContentBlockEvent } from "./contentBlock";
import { ConversationInfo } from "./conversation";

// Stream types
type StreamEnvelope<TType extends string, TData> = {
  type: TType;
  data: TData;
  seq?: number;
};

export type StreamMessage =
  | StreamEnvelope<"ack", ChatMessage>
  | StreamEnvelope<"refresh_conversation", ConversationInfo>
  | StreamEnvelope<
      "title",
      {
        id: string;
        title: string;
      }
    >
  | StreamEnvelope<"content_block", ContentBlockEvent>
  | StreamEnvelope<
      "done",
      {
        userMessageId: string;
        conversationId: string;
        assistantMessageId: string;
        lastMessageUpdatedAt: string;
        contentLength: number;
        reasoningLength: number;
        toolCallsLength: number;
      }
    >
  | StreamEnvelope<
      "error",
      {
        content: string; // 错误信息
      }
    >;

export type StreamMessageHandlerMap = {
  [type in StreamMessage["type"]]: (data: Extract<StreamMessage, { type: type }>["data"]) => void;
};
