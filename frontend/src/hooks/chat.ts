import { useEffect, useMemo, useRef } from "react";
import { useAppDispatch, useAppSelector } from "@/store/hooks";
import {
  addMessage,
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
import { updateConversationInfo } from "@/store/slices/conversationSlice";
import { chatAPI } from "@/services";
import {
  ChatInputFormValues,
  ChatMessage,
  SendMessageOptions,
  StreamMessage,
  ToolCallMessage,
} from "@/interfaces";

import { isEmpty, isNil, isPlainObject, omit } from "lodash-es";
import {
  buildFootnoteDefinition,
  getHistoryMessages,
  isUserRole,
  getDatetimeNow,
  isTitleCreatedByDefault,
} from "@/utils";
import { emitter, EventType } from "@/events";
import { TitleCreatedBy } from "@/constants";
import { useParams } from "react-router-dom";

export interface UseChatMessageOptions {
  conversationId?: string;
  historyLimit?: number;
}

export interface UseChatMessageReturn {
  abortMessage: () => void;
  reSendMessage: (
    index: number,
    message: ChatMessage,
    formData: Omit<ChatInputFormValues, "message">
  ) => Promise<void>;
  sendMessage: (
    values: ChatInputFormValues,
    options?: SendMessageOptions
  ) => Promise<void>;
}

export const useChatMessage = (
  options: UseChatMessageOptions = {}
): UseChatMessageReturn => {
  const { conversationId, historyLimit = 10 } = options;

  const dispatch = useAppDispatch();
  const { messages, isLoading, isStreaming } = useAppSelector(
    state => state.chat
  );

  const abortControllerRef = useRef<AbortController | null>(null);

  const resetState = () => {
    dispatch(setStreaming(false));
    dispatch(setLoading(false));
    dispatch(setReasoning(false));
    dispatch(setCallingTools(false));
  };

  const sendMessage = async (
    values: ChatInputFormValues,
    options?: SendMessageOptions
  ): Promise<void> => {
    const { index, createdBy, conversationIdOverride } = options || {};

    // 如果正在流式传输，先中止当前请求
    if (abortControllerRef.current && isStreaming) {
      abortControllerRef.current.abort();
      dispatch(clearLastMessage());
    }

    // 使用传入的 conversationIdOverride，否则使用 hook 初始化时的 conversationId
    const finalConversationId = conversationIdOverride ?? conversationId;

    // 添加用户消息
    const userMessage: ChatMessage = {
      role: "user",
      content: values.message,
      createdAt: getDatetimeNow(),
      messageMetadata: omit(values, ["message"]),
    };
    // dispatch(
    //   isNil(index)
    //     ? addMessage(userMessage)
    //     : addMessageAtIndex({ message: userMessage, index })
    // );

    // 添加空的助手消息用于流式传输
    const assistantMessage: ChatMessage = {
      role: "assistant",
      content: "",
      reasoning: "",
      createdAt: getDatetimeNow(),
      messageMetadata: omit(values, ["message"]),
    };
    // dispatch(addMessage(assistantMessage));
    dispatch(setStreaming(true));
    dispatch(setLoading(true));

    try {
      abortControllerRef.current = new AbortController();
      const history = getHistoryMessages(historyLimit, messages, index);
      const regenerateTitle =
        isEmpty(history) && isTitleCreatedByDefault(createdBy);

      // 开始流式传输
      await chatAPI.streamMessage(
        {
          ...values,
          history, // 发送最后几条消息作为上下文
          regenerateTitle,
          conversationId: finalConversationId,
        },
        (data: StreamMessage) => {
          if (!isPlainObject(data)) {
            console.warn("Invalid data:", data);
            return;
          }

          const { type } = data;
          const { status, content } = data.data || {};
          dispatch(setLoading(false)); // 收到响应
          if (type === "ack") {
            dispatch(addMessage(data.data as ChatMessage));
          } else if (type === "reasoning") {
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
          } else if (type === "title") {
            const { id, title } = data.data;
            dispatch(
              updateConversationInfo({
                id,
                title,
                createdBy: TitleCreatedBy.LLM,
              })
            );
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
      sendMessage({ ...formData, message: message.content }, { index });
    } else {
      // 如果是助手消息，则重新发送上一个用户消息
      const newIndex = index - 1;
      sendMessage(
        { ...formData, message: messages[newIndex].content },
        { index: newIndex }
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
    reSendMessage,
  };
};

export function useNewConversation() {
  const { conversationId } = useParams<{ conversationId?: string }>();
  const key = "ai:assistant:new_conversation";
  const isNewConversation = useMemo(
    () => sessionStorage.getItem(key) === "1",
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [key, conversationId] // 路由变化后，由于渲染同一个 ChatPage 实例，因此需要依赖 conversationId 来主动执行 useMemo
  );

  // 页面刷新后清除 isNewConversation 状态
  useEffect(() => {
    if (conversationId && isNewConversation) {
      sessionStorage.removeItem(key);
    }
  }, [conversationId, isNewConversation]);

  return {
    value: isNewConversation,
    setValue: (value: boolean) => {
      sessionStorage.setItem(key, value ? "1" : "0");
    },
    removeValue: () => {
      sessionStorage.removeItem(key);
    },
  };
}
