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
  resetChatState,
  updateMessageModifiedTime,
  setMessages,
} from "@/store/slices/chatSlice";
import { DEFAULT_CHAT_STATE } from "@/store/slices/chatSlice";
import {
  refreshConversionInList,
  removeConversationFromList,
  updateConversationInfo,
  updateConversationModifiedTime,
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

import { isEmpty } from "lodash-es";
import {
  buildFootnoteDefinition,
  getHistoryMessageIds,
  isUserRole,
  isTitleCreatedByDefault,
  getRemovedMessageIds,
} from "@/utils";
import { emitter, EventType } from "@/events";
import { MessageStatus, TitleCreatedBy } from "@/constants";
import { useNavigate, useParams } from "react-router-dom";
import { useMemoizedFn, useRequest } from "ahooks";

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

export const useChatState = (conversationId: string) => {
  return useAppSelector(
    state => state.chat[conversationId] || DEFAULT_CHAT_STATE
  );
};

export const useChatMessage = (options: UseChatMessageOptions) => {
  const { conversationId, historyLimit = 10 } = options;
  const dispatch = useAppDispatch();
  const { messages, isLoading, isStreaming } = useChatState(conversationId);

  const abortControllerRef = useRef<AbortController | null>(null);

  const resetState = useMemoizedFn(() => {
    dispatch(resetChatState({ conversationId, data: undefined }));
  });

  const abortMessage = useMemoizedFn((): void => {
    if (abortControllerRef.current && isStreaming) {
      abortControllerRef.current.abort();
      // 服务端 llm api 还没响应，则清除最后一条消息
      const lastMessage = lastMessageCheck(messages);
      if (lastMessage && lastMessage.id && isLoading) {
        dispatch(clearLastMessage({ conversationId, data: undefined }));
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

      dispatch(setStreaming({ conversationId, data: true }));
      dispatch(setLoading({ conversationId, data: true }));

      try {
        abortControllerRef.current = new AbortController();
        const historyIds = getHistoryMessageIds(historyLimit, messages, index);
        const removedMessageIds = getRemovedMessageIds(messages, index);
        const regenerateTitle =
          isEmpty(history) && isTitleCreatedByDefault(createdBy);

        // 对于在指定位置修改 message 或 重发 message 的场景，需要删除改位置之后的所有 message
        if (!isEmpty(removedMessageIds)) {
          dispatch(clearMessagesAfterIndex({ conversationId, data: index! }));
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
              dispatch(setLoading({ conversationId, data: false })); // 收到响应
            }

            if (type === "ack") {
              const message = data.data as ChatMessage;
              if (isUserRole(message.role) && !isEmpty(removedMessageIds)) {
                dispatch(
                  removeMessageById({
                    conversationId,
                    data: removedMessageIds[0],
                  })
                );
              }
              dispatch(
                addMessage({
                  conversationId,
                  data: { ...message, defaultOpen: true },
                })
              );
              dispatch(
                updateMessageModifiedTime({
                  conversationId,
                  data: message.updateAt,
                })
              );
            } else if (type === "refresh_conversation") {
              dispatch(refreshConversionInList(data.data as ConversationInfo));
            } else if (type === "reasoning") {
              // 思考内容
              if (status === "start") {
                dispatch(setReasoning({ conversationId, data: true }));
              } else if (status === "done") {
                emitter.emit(EventType.ReasoningDone);
                dispatch(setReasoning({ conversationId, data: false }));
              }
              dispatch(
                appendReasoningToLastMessage({
                  conversationId,
                  data: content || "",
                })
              );
            } else if (type === "content") {
              dispatch(
                appendContentToLastMessage({
                  conversationId,
                  data: content || "",
                })
              );
            } else if (type === "sources") {
              // 知识库搜索结果
              dispatch(setSources({ conversationId, data: data.data }));
              const sourceStr = buildFootnoteDefinition(data.data);
              dispatch(
                prependSourceToLastReasoningMessage({
                  conversationId,
                  data: sourceStr,
                })
              );
              dispatch(
                prependContentToLastMessage({ conversationId, data: sourceStr })
              );
            } else if (type === "tool_call") {
              const { role } = data.data;
              dispatch(setCallingTools({ conversationId, data: true }));
              if (!role && status === "done") {
                emitter.emit(EventType.ToolCallDone);
                dispatch(setCallingTools({ conversationId, data: false }));
              }
              dispatch(
                appendToolCallToLastMessage({
                  conversationId,
                  data: data.data as ToolCallMessage,
                })
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
              const { lastMessageUpdatedAt } = data.data;
              // 流结束
              dispatch(
                updateMessageStatus({
                  conversationId,
                  data: MessageStatus.DONE,
                })
              );
              dispatch(
                updateMessageModifiedTime({
                  conversationId,
                  data: lastMessageUpdatedAt,
                })
              );
              dispatch(
                updateConversationModifiedTime({
                  conversationId,
                  lastMessageUpdatedAt,
                })
              );
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

export const useCachedRequest = (conversationId: string) => {
  // 页面刷新后清除 isNewConversation 状态
  const { cacheData: conversationState, clearCacheData } = useNewConversation();
  const navigate = useNavigate();
  const { sendMessage } = useChatMessage({ conversationId });
  const { messageLoaded } = useChatState(conversationId);
  const dispatch = useAppDispatch();

  useEffect(() => {
    // 如果是新对话，则发送消息
    if (conversationState.isNewConversation) {
      clearCacheData();
      sendMessage(conversationState.values, {
        createdBy: conversationState.createdBy,
      });
    }
  }, [conversationState, sendMessage, clearCacheData]);

  const { run: loadMessages } = useRequest(chatAPI.getConversationMessages, {
    manual: true,
    onSuccess: data => {
      dispatch(setMessages({ conversationId, data }));
    },
    onError: error => {
      console.info("error", error);
      if ((error as { code?: number }).code === 404) {
        navigate("/chat", { replace: true });
        // 删除会话列表中的会话
        dispatch(removeConversationFromList(conversationId));
      }
    },
  });

  useEffect(() => {
    // 排除新对话和没有 conversationId 的情况
    if (conversationState.isNewConversation || !conversationId) {
      return;
    }

    // 如果消息已加载，则不重新加载
    if (messageLoaded) {
      return;
    }

    loadMessages(conversationId);
  }, [loadMessages, conversationState, conversationId, messageLoaded]);
};
