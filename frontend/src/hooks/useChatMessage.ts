import { useRef } from "react";
import { useAppDispatch, useAppSelector } from "@/store/hooks";
import {
  addMessage,
  appendToLastMessage,
  clearLastMessage,
  setLoading,
  setSources,
  setStreaming,
} from "@/store/slices/chatSlice";
import { chatAPI } from "@/services/api";
import {
  ChatInputFormValues,
  ChatMessage as ChatMessageType,
  StreamMessage,
} from "@/types";

export interface UseChatMessageOptions {
  historyLimit?: number;
}

export interface UseChatMessageReturn {
  sendMessage: (values: ChatInputFormValues) => Promise<void>;
  abortMessage: () => void;
  isStreaming: boolean;
  isLoading: boolean;
}

export const useChatMessage = (
  options: UseChatMessageOptions = {}
): UseChatMessageReturn => {
  const { historyLimit = 10 } = options;

  const dispatch = useAppDispatch();
  const { messages, isLoading, isStreaming, sessionId } = useAppSelector(
    state => state.chat
  );

  const abortControllerRef = useRef<AbortController | null>(null);

  const sendMessage = async (values: ChatInputFormValues): Promise<void> => {
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
    };
    dispatch(addMessage(userMessage));

    // 添加空的助手消息用于流式传输
    const assistantMessage: ChatMessageType = {
      role: "assistant",
      content: "",
      timestamp: new Date().toISOString(),
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
          // 处理流式数据
          if (data.type === "content") {
            // 回答内容
            dispatch(appendToLastMessage(data.data));
            dispatch(setLoading(false));
          } else if (data.type === "sources") {
            // 知识库搜索结果
            dispatch(setSources(data.data));
          } else if (data.type === "done") {
            // 流结束
            dispatch(setStreaming(false));
            dispatch(setLoading(false));
          }
        },
        (error: Error) => {
          // 流错误
          console.error("Stream error:", error);
          dispatch(setStreaming(false));
          dispatch(setLoading(false));
        },
        () => {
          // 流结束
          dispatch(setStreaming(false));
          dispatch(setLoading(false));
        },
        abortControllerRef.current
      );
    } catch (error) {
      console.error("Failed to send message:", error);
      dispatch(setStreaming(false));
      dispatch(setLoading(false));
    }
  };

  const abortMessage = (): void => {
    if (abortControllerRef.current && isStreaming) {
      abortControllerRef.current.abort();
      dispatch(clearLastMessage());
      dispatch(setStreaming(false));
      dispatch(setLoading(false));
    }
  };

  return {
    sendMessage,
    abortMessage,
    isStreaming,
    isLoading,
  };
};
