import { useRef } from "react";
import { useAppDispatch, useAppSelector } from "@/store/hooks";
import {
  addMessage,
  addMessageAtIndex,
  appendContentToLastMessage,
  appendReasoningToLastMessage,
  prependSourceToLastReasoningMessage,
  clearLastMessage,
  prependContentToLastMessage,
  appendToolCallToLastMessage,
  setLoading,
  setReasoning,
  setSources,
  setStreaming,
  setCallingTools,
} from "@/store/slices/chatSlice";
import { chatAPI } from "@/services";
import {
  ChatInputFormValues,
  ChatMessage,
  StreamMessage,
  ToolCallMessage,
} from "@/interfaces";

import { isNil, isPlainObject, omit } from "lodash-es";
import {
  buildFootnoteDefinition,
  getHistoryMessages,
  isUserRole,
} from "@/utils";
import { emitter, EventType } from "@/events";

export interface UseChatMessageOptions {
  historyLimit?: number;
}

export interface UseChatMessageReturn {
  isLoading: boolean;
  isStreaming: boolean;
  isReasoning: boolean;
  isCallingTools: boolean;
  messages: ChatMessage[];
  abortMessage: () => void;
  reSendMessage: (
    index: number,
    message: ChatMessage,
    formData: Omit<ChatInputFormValues, "message">
  ) => Promise<void>;
  sendMessage: (values: ChatInputFormValues, index?: number) => Promise<void>;
}

export const useChatMessage = (
  options: UseChatMessageOptions = {}
): UseChatMessageReturn => {
  const { historyLimit = 10 } = options;

  const dispatch = useAppDispatch();
  const {
    messages,
    isLoading,
    isStreaming,
    isReasoning,
    isCallingTools,
    conversationInfo,
  } = useAppSelector(state => state.chat);

  const abortControllerRef = useRef<AbortController | null>(null);

  const resetState = () => {
    dispatch(setStreaming(false));
    dispatch(setLoading(false));
    dispatch(setReasoning(false));
    dispatch(setCallingTools(false));
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
    const userMessage: ChatMessage = {
      role: "user",
      content: values.message,
      timestamp: new Date().toISOString(),
      messageMetadata: omit(values, ["message"]),
    };
    dispatch(
      isNil(index)
        ? addMessage(userMessage)
        : addMessageAtIndex({ message: userMessage, index })
    );

    // 添加空的助手消息用于流式传输
    const assistantMessage: ChatMessage = {
      role: "assistant",
      content: "",
      reasoning: "",
      timestamp: new Date().toISOString(),
      messageMetadata: omit(values, ["message"]),
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
          conversationId: conversationInfo?.id || undefined,
          history: getHistoryMessages(historyLimit, messages, index), // 发送最后几条消息作为上下文
        },
        (data: StreamMessage) => {
          if (!isPlainObject(data)) {
            console.warn("Invalid data:", data);
            return;
          }

          const { type } = data;
          const { status, content } = data.data || {};
          dispatch(setLoading(false)); // 收到响应
          if (type === "reasoning") {
            // 思考内容
            if (status === "start") {
              dispatch(setReasoning(true));
            } else if (status === "done") {
              dispatch(setReasoning(false));
              emitter.emit(EventType.ReasoningDone);
            }
            dispatch(appendReasoningToLastMessage(content || ""));
          } else if (type === "content") {
            dispatch(appendContentToLastMessage(content || ""));
          } else if (type === "sources") {
            // 知识库搜索结果
            dispatch(setSources(data.data));
            const sourceStr = buildFootnoteDefinition(data.data);
            dispatch(prependSourceToLastReasoningMessage(sourceStr));
            dispatch(prependContentToLastMessage(sourceStr));
          } else if (type === "tool_call") {
            const { role } = data.data;
            dispatch(setCallingTools(true));
            if (!role && status === "done") {
              dispatch(setCallingTools(false));
              emitter.emit(EventType.ToolCallDone);
            }
            dispatch(appendToolCallToLastMessage(data.data as ToolCallMessage));
          } else if (type === "done") {
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
    message: ChatMessage,
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
      isLoading && dispatch(clearLastMessage());
      resetState();
    }
  };

  return {
    sendMessage,
    abortMessage,
    isStreaming,
    isLoading,
    isReasoning,
    isCallingTools,
    reSendMessage,
    messages,
  };
};
