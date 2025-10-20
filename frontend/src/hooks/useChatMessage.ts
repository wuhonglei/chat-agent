import { useRef } from "react";
import { useAppDispatch, useAppSelector } from "@/store/hooks";
import {
  addMessage,
  addMessageAtIndex,
  appendToLastMessage,
  appendToLastReasoningMessage,
  prependSourceToLastReasoningMessage,
  clearLastMessage,
  prependToLastMessage,
  setLoading,
  setReasoning,
  setSources,
  setStreaming,
} from "@/store/slices/chatSlice";
import { chatAPI } from "@/services";
import {
  ChatInputFormValues,
  ChatMessage as ChatMessageType,
  StreamMessage,
} from "@/interfaces";

import { isNil, omit } from "lodash-es";
import { buildFootnoteDefinition, isUserRole } from "@/utils";

export interface UseChatMessageOptions {
  historyLimit?: number;
}

export interface UseChatMessageReturn {
  isLoading: boolean;
  isStreaming: boolean;
  isReasoning: boolean;
  messages: ChatMessageType[];
  abortMessage: () => void;
  reSendMessage: (
    index: number,
    message: ChatMessageType,
    formData: Omit<ChatInputFormValues, "message">
  ) => Promise<void>;
  sendMessage: (values: ChatInputFormValues, index?: number) => Promise<void>;
}

export const useChatMessage = (
  options: UseChatMessageOptions = {}
): UseChatMessageReturn => {
  const { historyLimit = 10 } = options;

  const dispatch = useAppDispatch();
  const { messages, isLoading, isStreaming, isReasoning, sessionId } =
    useAppSelector(state => state.chat);

  const abortControllerRef = useRef<AbortController | null>(null);

  const resetState = () => {
    dispatch(setStreaming(false));
    dispatch(setLoading(false));
    dispatch(setReasoning(false));
  };

  const sendMessage = async (
    values: ChatInputFormValues,
    index?: number
  ): Promise<void> => {
    // 如果正在流式传输，先中止当前请求
    if (abortControllerRef.current && isStreaming) {
      abortControllerRef.current.abort();
      dispatch(clearLastMessage());
    }

    // 添加用户消息
    const userMessage: ChatMessageType = {
      role: "user",
      content: values.message,
      timestamp: new Date().toISOString(),
      metadata: omit(values, ["message"]),
    };
    dispatch(
      isNil(index)
        ? addMessage(userMessage)
        : addMessageAtIndex({ message: userMessage, index })
    );

    // 添加空的助手消息用于流式传输
    const assistantMessage: ChatMessageType = {
      role: "assistant",
      content: "",
      reasoning: "",
      timestamp: new Date().toISOString(),
      metadata: omit(values, ["message"]),
    };
    dispatch(addMessage(assistantMessage));
    dispatch(setStreaming(true));
    dispatch(setLoading(true));

    try {
      abortControllerRef.current = new AbortController();

      // 开始流式传输
      await chatAPI.streamMessage(
        {
          ...values,
          sessionId: sessionId || undefined,
          history: messages.slice(-historyLimit), // 发送最后几条消息作为上下文
        },
        (data: StreamMessage) => {
          if (data.type === "reasoning") {
            // 思考内容
            dispatch(appendToLastReasoningMessage(data.data));
            dispatch(setReasoning(true));
            dispatch(setLoading(false));
          } else if (data.type === "content") {
            // 回答内容
            dispatch(appendToLastMessage(data.data));
            dispatch(setLoading(false));
            dispatch(setReasoning(false));
          } else if (data.type === "sources") {
            // 知识库搜索结果
            dispatch(setSources(data.data));
            dispatch(prependSourceToLastReasoningMessage(data.data));
            dispatch(prependToLastMessage(buildFootnoteDefinition(data.data)));
          } else if (data.type === "done") {
            // 流结束
            resetState();
          }
        },
        (error: Error) => {
          // 流错误
          console.error("Stream error:", error);
          resetState();
        },
        () => {
          // 流结束
          resetState();
        },
        abortControllerRef.current
      );
    } catch (error) {
      console.error("Failed to send message:", error);
      resetState();
    }
  };

  const reSendMessage = async (
    index: number,
    message: ChatMessageType,
    formData: Omit<ChatInputFormValues, "message">
  ): Promise<void> => {
    if (isUserRole(message.role)) {
      sendMessage({ ...formData, message: message.content }, index);
    } else {
      // 如果是助手消息，则重新发送上一个用户消息
      const newIndex = index - 1;
      sendMessage(
        { ...formData, message: messages[newIndex].content },
        newIndex
      );
    }
  };

  const abortMessage = (): void => {
    if (abortControllerRef.current && isStreaming) {
      abortControllerRef.current.abort();
      dispatch(clearLastMessage());
      resetState();
    }
  };

  return {
    sendMessage,
    abortMessage,
    isStreaming,
    isLoading,
    isReasoning,
    reSendMessage,
    messages,
  };
};
