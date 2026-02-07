import {
  ChatInputConfig,
  ChatInputFormValues,
  ChatMessage,
  ConversationInfo,
  NewConversationCache,
  SendMessageOptions,
  StreamMessage,
  StreamMessageHandlerMap,
} from "@/interfaces";
import { chatAPI } from "@/services";
import { useAppDispatch, useAppSelector } from "@/store/hooks";
import {
  addMessage,
  appendComponentToolCallToLastMessage,
  appendContentToLastMessage,
  appendMcpToolCallToLastMessage,
  appendReasoningToLastMessage,
  clearLastMessage,
  clearMessagesAfterIndex,
  DEFAULT_CHAT_STATE,
  lastMessageCheck,
  removeMessageById,
  resetChatState,
  setCallingComponentTools,
  setCallingMcpTools,
  setComponentToolCallsDuration,
  setComponentToolsTokenStats,
  setLoading,
  setMcpToolCallsDuration,
  setMcpToolsTokenStats,
  setMessages,
  setReasoning,
  setReasoningDuration,
  setStreaming,
  setTempMessages,
  updateContentDuration,
  updateMessageModifiedTime,
  updateMessageStatus,
  updateMessageTokenStats,
} from "@/store/slices/chatSlice";
import {
  getConversationDetail,
  refreshConversionInList,
  removeConversationFromList,
  updateConversationInfo,
  updateConversationModifiedTime,
} from "@/store/slices/conversationSlice";
import { useEffect, useMemo, useRef } from "react";

import { componentToolsForBackend } from "@/componentTools/helper";
import { emitter, EventType } from "@/events";
import { db } from "@/indexDB";
import { MessageStatus, TitleCreatedBy } from "@/interfaces";
import type { ToolCallMessage } from "@/interfaces/tooCall";
import {
  getHistoryMessageIds,
  getRemovedMessageIds,
  isTitleCreatedByUser,
  isUserRole,
  reportError,
  reportEvent,
} from "@/utils";
import type { UnknownAction } from "@reduxjs/toolkit";
import { useMemoizedFn, useRequest } from "ahooks";
import { App } from "antd";
import dayjs from "dayjs";
import { isEmpty } from "lodash-es";
import { useParams } from "react-router-dom";

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
  abortMessage: (conversationId: string) => void;
  reSendMessage: (index: number, message: ChatMessage, formData: ChatInputConfig) => Promise<void>;
  sendMessage: (values: ChatInputFormValues, options?: SendMessageOptions) => Promise<void>;
}

/** 工具调用（mcp / component）通用处理器工厂，消除重复逻辑 */
function createToolCallHandler<TTokenStats>(
  dispatch: ReturnType<typeof useAppDispatch>,
  conversationId: string,
  config: {
    setCalling: (payload: { conversationId: string; data: boolean }) => UnknownAction;
    appendToLast: (payload: { conversationId: string; data: ToolCallMessage }) => UnknownAction;
    setDuration: (payload: { conversationId: string; data: number }) => UnknownAction;
    setTokenStats: (payload: { conversationId: string; data: TTokenStats }) => UnknownAction;
    doneEvent: EventType;
  }
): (data: ToolCallMessage) => void {
  return (data: ToolCallMessage) => {
    const { role } = data;
    dispatch(config.setCalling({ conversationId, data: true }));
    if (!role && data?.status === "done") {
      emitter.emit(config.doneEvent);
      dispatch(config.setCalling({ conversationId, data: false }));
      if (data.duration) {
        dispatch(config.setDuration({ conversationId, data: data.duration }));
      }
      if (data?.tokenStats) {
        dispatch(
          config.setTokenStats({
            conversationId,
            data: data.tokenStats as TTokenStats,
          })
        );
      }
    } else {
      dispatch(config.appendToLast({ conversationId, data }));
    }
  };
}

export const useChatState = (conversationId: string) => {
  return useAppSelector(state => state.chat[conversationId] || DEFAULT_CHAT_STATE);
};

export const useChatMessage = (options: UseChatMessageOptions) => {
  const { conversationId, historyLimit = 100 } = options;
  const dispatch = useAppDispatch();
  const { message } = App.useApp();
  const { messages, isLoading, isStreaming } = useChatState(conversationId);

  const abortControllerRef = useRef<AbortController | null>(null);

  const resetState = useMemoizedFn(conversationId => {
    dispatch(resetChatState({ conversationId, data: undefined }));
  });

  const abortMessage = useMemoizedFn((conversationId): void => {
    if (abortControllerRef.current && isStreaming) {
      abortControllerRef.current.abort();
      // 服务端 llm api 还没响应，则清除最后一条消息
      const lastMessage = lastMessageCheck(messages);
      if (lastMessage && lastMessage.id && isLoading) {
        dispatch(clearLastMessage({ conversationId, data: undefined }));
        chatAPI.deleteMessage(lastMessage.id);
      }
      resetState(conversationId);
    }
  });

  const sendMessage = useMemoizedFn(
    async (values: ChatInputFormValues, options?: SendMessageOptions): Promise<void> => {
      const { index, createdBy } = options || {};

      // 如果正在流式传输，先中止当前请求
      if (abortControllerRef.current && isStreaming) {
        abortMessage(conversationId);
      }

      dispatch(setStreaming({ conversationId, data: true }));
      dispatch(setLoading({ conversationId, data: true }));

      try {
        abortControllerRef.current = new AbortController();
        const historyIds = getHistoryMessageIds(historyLimit, messages, index);
        const removedMessageIds = getRemovedMessageIds(messages, index);
        const regenerateTitle = isEmpty(historyIds) && !isTitleCreatedByUser(createdBy);

        // 对于在指定位置修改 message 或 重发 message 的场景，需要删除该位置之后的所有 message
        if (!isEmpty(removedMessageIds)) {
          dispatch(clearMessagesAfterIndex({ conversationId, data: index! }));
        }

        // 流式传输消息处理器映射表
        const messageHandlers: StreamMessageHandlerMap = {
          // 添加消息
          ack: data => {
            if (isUserRole(data.role) && !isEmpty(removedMessageIds)) {
              // 收到新的用户消息，删除 store 中旧的用户消息
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
                data,
              })
            );
            dispatch(
              updateMessageModifiedTime({
                conversationId,
                data: data.updatedAt,
              })
            );
          },

          // 刷新会话列表
          refresh_conversation: data => {
            dispatch(refreshConversionInList(data as ConversationInfo));
          },

          // 更新会话标题
          title: data => {
            const { id, title } = data;
            dispatch(
              updateConversationInfo({
                id,
                title,
                createdBy: TitleCreatedBy.LLM,
              })
            );
          },

          // Mcp 工具调用
          mcp_tool_call: createToolCallHandler(dispatch, conversationId, {
            setCalling: setCallingMcpTools,
            appendToLast: appendMcpToolCallToLastMessage,
            setDuration: setMcpToolCallsDuration,
            setTokenStats: setMcpToolsTokenStats,
            doneEvent: EventType.McpToolCallDone,
          }),

          // 组件工具调用
          component_tool_call: createToolCallHandler(dispatch, conversationId, {
            setCalling: setCallingComponentTools,
            appendToLast: appendComponentToolCallToLastMessage,
            setDuration: setComponentToolCallsDuration,
            setTokenStats: setComponentToolsTokenStats,
            doneEvent: EventType.ComponentToolCallDone,
          }),

          // 更新消息思考内容
          reasoning: (data = {}) => {
            const { status, content, duration } = data;
            if (status === "start") dispatch(setReasoning({ conversationId, data: true }));
            else if (status === "done") {
              emitter.emit(EventType.ReasoningDone);
              dispatch(setReasoning({ conversationId, data: false }));
              if (duration) dispatch(setReasoningDuration({ conversationId, data: duration }));
            }
            dispatch(
              appendReasoningToLastMessage({
                conversationId,
                data: content ?? "",
              })
            );
          },

          // 更新消息内容
          content: ({ content } = {}) =>
            dispatch(
              appendContentToLastMessage({
                conversationId,
                data: content ?? "",
              })
            ),

          // 本次消息流式传输结束
          done: data => {
            const { lastMessageUpdatedAt, tokenStats } = data;
            dispatch(updateMessageStatus({ conversationId, data: MessageStatus.Done }));
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
            dispatch(updateMessageTokenStats({ conversationId, data: tokenStats }));
            dispatch(updateContentDuration({ conversationId, data: data.contentDuration }));
            resetState(conversationId);
            reportEvent("message_stream_done", data);
          },
          error: data => {
            const { content } = data || {};
            if (content) {
              message.error(content);
            }
            // 流式输出时，返回消息类型为 error 时，上报错误
            reportError("Stream Error", { error: data, conversationId });
          },
        };

        // 开始流式传输
        await chatAPI.streamMessage(
          {
            ...values,
            historyIds, // 发送最后几条消息作为上下文
            regenerateTitle,
            removedMessageIds,
            conversationId,
            componentToolsForBackend,
          },
          (data: StreamMessage) => {
            const { type, data: messageData } = data;

            // 处理加载状态
            if (!["ack", "refresh_conversation", "title"].includes(type)) {
              dispatch(setLoading({ conversationId, data: false }));
            }

            // 执行对应的消息处理器
            const handler = messageHandlers[type];
            if (handler) {
              (handler as (data: unknown) => void)(messageData);
            } else {
              console.warn(`Unknown message type: ${type}`);
              reportError("streamMessage onMessage Unknown Message Type", {
                type,
                conversationId,
              });
            }
          },
          (error: Error) => {
            // 流式传输错误
            reportError("streamMessage onError", {
              error: error,
              conversationId,
            });
            resetState(conversationId);
          },
          () => {
            // 流结束
            resetState(conversationId);
          },
          abortControllerRef.current
        );
      } catch (error) {
        console.error("Failed to send message:", error);
        reportError("Failed to send message", {
          error: error,
          conversationId,
        });
        resetState(conversationId);
      }
    }
  );

  const reSendMessage = useMemoizedFn(
    async (index: number, message: ChatMessage, formData: ChatInputConfig): Promise<void> => {
      if (isUserRole(message.role)) {
        sendMessage({ ...formData, content: message.content }, { index });
      } else {
        // 如果是助手消息，则重新发送上一个用户消息
        const newIndex = index - 1;
        sendMessage({ ...formData, content: messages[newIndex].content }, { index: newIndex });
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
      } catch {
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

export const useConversationInfo = (conversationId: string) => {
  const conversationInfo = useAppSelector(state => state.conversation.conversationInfo);
  const dispatch = useAppDispatch();
  // 页面刷新时，conversationInfo 为空，则获取 conversationInfo
  const empty = isEmpty(conversationInfo);
  useEffect(() => {
    if (empty && conversationId) {
      dispatch(getConversationDetail(conversationId));
    }
  }, [conversationId, empty, dispatch]);
  return conversationInfo;
};

export const useCachedRequest = (conversationId: string, conversationInfo: ConversationInfo | null) => {
  // 页面刷新后清除 isNewConversation 状态
  const { cacheData: conversationState, clearCacheData } = useNewConversation();
  const isNewConversation = conversationState.isNewConversation;
  const { sendMessage } = useChatMessage({ conversationId });
  const { messageLoaded } = useChatState(conversationId);
  const lastMessageUpdateAt = conversationInfo?.lastMessageUpdatedAt;
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

  const { run: loadMessages } = useRequest(
    (conversationId: string) => {
      console.info("starting to load messages", conversationId);
      return chatAPI.getConversationMessages(conversationId);
    },
    {
      manual: true,
      onSuccess: data => {
        dispatch(setMessages({ conversationId, data }));
      },
      onError: error => {
        console.info("error", error);
        if ((error as { code?: number }).code === 404) {
          // 删除会话列表中的会话
          dispatch(removeConversationFromList(conversationId));
        }
      },
    }
  );

  useEffect(() => {
    // 排除新对话和没有 conversationId 的情况
    if (isNewConversation || !conversationId) {
      return;
    }

    // 如果消息已加载到 store 中, 直接使用 store 中的数据
    if (messageLoaded) {
      console.info("message already loaded", conversationId);
      return;
    }

    db.conversationMessages
      .get(conversationId)
      .then(data => {
        // 首次刷新时，conversationInfo 还未获取到，则不加载消息
        if (!lastMessageUpdateAt) {
          if (!isEmpty(data?.data?.messages)) {
            dispatch(
              setTempMessages({
                conversationId,
                data: data?.data?.messages as ChatMessage[],
              })
            );
            console.info("use temp messages from indexDB", conversationId);
          } else {
            console.info("conversationInfo not loaded yet, will load messages later", conversationId);
          }
          return;
        }

        // indexDB 中没有数据，则加载消息
        if (!data?.data || !data.data.lastMessageUpdateAt) {
          loadMessages(conversationId);
          return;
        }

        // indexDB 中的数据比较旧，则加载消息
        const { lastMessageUpdateAt: cacheLastMessageUpdateAt, messages } = data.data;
        if (dayjs(cacheLastMessageUpdateAt).isBefore(dayjs(lastMessageUpdateAt))) {
          loadMessages(conversationId);
          return;
        }

        // indexDB 中的数据比较新，则直接使用 indexDB 中的数据
        dispatch(setMessages({ conversationId, data: messages }));
        console.info("use cached data", conversationId);
      })
      .catch(error => {
        console.info("error getting messages from indexedDB", error);
        loadMessages(conversationId);
      });
  }, [isNewConversation, conversationId, messageLoaded, lastMessageUpdateAt, dispatch, loadMessages]);
};
