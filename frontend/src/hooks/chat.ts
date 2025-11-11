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
  updateMessageStatus,
  lastMessageCheck,
  removeMessageById,
  clearMessagesAfterIndex,
} from "@/store/slices/chatSlice";
import {
  refreshConversionInList,
  updateConversationInfo,
} from "@/store/slices/conversationSlice";
import { chatAPI } from "@/services";
import {
  ChatInputConfig,
  ChatInputFormValues,
  ChatMessage,
  ConversationInfo,
  NewConversationCache,
  SendMessageOptions,
  StreamMessage,
  ToolCallMessage,
} from "@/interfaces";

import { isEmpty, isPlainObject } from "lodash-es";
import {
  buildFootnoteDefinition,
  getHistoryMessageIds,
  isUserRole,
  isTitleCreatedByDefault,
  getRemovedMessageIds,
} from "@/utils";
import { emitter, EventType } from "@/events";
import { MessageStatus, TitleCreatedBy } from "@/constants";
import { useParams } from "react-router-dom";
import { useMemoizedFn } from "ahooks";

/**
 * 用于控制 ChatPage 的渲染
 */
export interface UseChatMessageOptions {
  conversationId: string;
  historyLimit?: number;
}

/**
 * 用于控制 ChatPage 的渲染
 */
export interface UseChatMessageReturn {
  abortMessage: () => void;
  reSendMessage: (
    index: number,
    message: ChatMessage,
    formData: ChatInputConfig
  ) => Promise<void>;
  sendMessage: (
    values: ChatInputFormValues,
    options?: SendMessageOptions
  ) => Promise<void>;
}

/**
 * 用于控制 ChatPage 的渲染
 */
export const useChatMessage = (
  options: UseChatMessageOptions
): UseChatMessageReturn => {
  const { conversationId, historyLimit = 10 } = options;

  const dispatch = useAppDispatch();
  const { messages, isLoading, isStreaming } = useAppSelector(
    state => state.chat
  );

  const abortControllerRef = useRef<AbortController | null>(null);

  const resetState = useMemoizedFn(() => {
    dispatch(setStreaming(false));
    dispatch(setLoading(false));
    dispatch(setReasoning(false));
    dispatch(setCallingTools(false));
  });

  const abortMessage = useMemoizedFn((): void => {
    if (abortControllerRef.current && isStreaming) {
      abortControllerRef.current.abort();
      // 服务端 llm api 还没响应，则清除最后一条消息
      const lastMessage = lastMessageCheck(messages);
      if (lastMessage && lastMessage.id && isLoading) {
        dispatch(clearLastMessage());
        chatAPI.deleteMessage(lastMessage.id);
      }
      resetState();
    }
  });

  const sendMessage = useMemoizedFn(
    async (
      values: ChatInputFormValues,
      options?: SendMessageOptions
    ): Promise<void> => {
      const { index, createdBy } = options || {};

      // 如果正在流式传输，先中止当前请求
      if (abortControllerRef.current && isStreaming) {
        abortMessage();
      }

      dispatch(setStreaming(true));
      dispatch(setLoading(true));

      try {
        abortControllerRef.current = new AbortController();
        const historyIds = getHistoryMessageIds(historyLimit, messages, index);
        const removedMessageIds = getRemovedMessageIds(messages, index);
        const regenerateTitle =
          isEmpty(history) && isTitleCreatedByDefault(createdBy);

        // 对于在指定位置修改 message 或 重发 message 的场景，需要删除改位置之后的所有 message
        if (!isEmpty(removedMessageIds)) {
          dispatch(clearMessagesAfterIndex(index!));
        }

        // 开始流式传输
        await chatAPI.streamMessage(
          {
            ...values,
            historyIds, // 发送最后几条消息作为上下文
            regenerateTitle,
            removedMessageIds,
            conversationId,
          },
          (data: StreamMessage) => {
            const { type } = data;
            const { status, content } = data.data || {};
            if (!["ack", "refresh_conversation"].includes(type)) {
              dispatch(setLoading(false)); // 收到响应
            }

            if (type === "ack") {
              const message = data.data as ChatMessage;
              if (isUserRole(message.role) && !isEmpty(removedMessageIds)) {
                dispatch(removeMessageById(removedMessageIds[0]));
              }
              dispatch(addMessage({ ...message, defaultOpen: true }));
            } else if (type === "refresh_conversation") {
              dispatch(refreshConversionInList(data.data as ConversationInfo));
            } else if (type === "reasoning") {
              // 思考内容
              if (status === "start") {
                dispatch(setReasoning(true));
              } else if (status === "done") {
                emitter.emit(EventType.ReasoningDone);
                dispatch(setReasoning(false));
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
                emitter.emit(EventType.ToolCallDone);
                dispatch(setCallingTools(false));
              }
              dispatch(
                appendToolCallToLastMessage(data.data as ToolCallMessage)
              );
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
              dispatch(updateMessageStatus(MessageStatus.DONE));
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
    }
  );

  const reSendMessage = useMemoizedFn(
    async (
      index: number,
      message: ChatMessage,
      formData: ChatInputConfig
    ): Promise<void> => {
      if (isUserRole(message.role)) {
        sendMessage({ ...formData, content: message.content }, { index });
      } else {
        // 如果是助手消息，则重新发送上一个用户消息
        const newIndex = index - 1;
        sendMessage(
          { ...formData, content: messages[newIndex].content },
          { index: newIndex }
        );
      }
    }
  );

  return {
    sendMessage,
    abortMessage,
    reSendMessage,
  };
};

const NEW_CONVERSATION_CACHE_KEY = "ai:assistant:new_conversation";
/**
 * 用于判断是否是新对话
 * @returns {boolean} 是否是新对话
 */
export function useNewConversation() {
  const { conversationId } = useParams<{ conversationId?: string }>();
  const conversationState = useMemo<NewConversationCache>(
    () => {
      const defaultData = {
        isNewConversation: false,
      } as const;
      try {
        const cacheStr = sessionStorage.getItem(NEW_CONVERSATION_CACHE_KEY);
        if (!cacheStr) {
          return defaultData;
        }
        const cacheData: NewConversationCache = JSON.parse(cacheStr);
        if (!cacheData.isNewConversation) {
          return defaultData;
        }

        // 如果缓存数据过期，则清除
        if (Date.now() - cacheData.insertAt > 1000 * 5) {
          return defaultData;
        }

        return cacheData;
      } catch (error) {
        return defaultData;
      } finally {
        // console.info("conversationId", conversationId);
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [conversationId] // 路由变化后，由于渲染同一个 ChatPage 实例，因此需要依赖 conversationId 来主动执行 useMemo
  );

  const setCacheData = useMemoizedFn((data: NewConversationCache) => {
    try {
      sessionStorage.setItem(NEW_CONVERSATION_CACHE_KEY, JSON.stringify(data));
    } catch (error) {
      console.error("Failed to set new conversation cache:", error);
    }
  });

  const clearCacheData = useMemoizedFn(() => {
    sessionStorage.removeItem(NEW_CONVERSATION_CACHE_KEY);
  });

  return {
    cacheData: conversationState,
    setCacheData,
    clearCacheData,
  };
}
