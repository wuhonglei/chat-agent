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
  appendContentBlockToLastMessage,
  clearMessagesAfterIndex,
  DEFAULT_CHAT_STATE,
  removeMessageById,
  replaceMessageById,
  resetChatState,
  setLoading,
  setMessages,
  setStreaming,
  setTempMessages,
  updateMessageModifiedTime,
  updateMessageStatus,
} from "@/store/slices/chatSlice";
import {
  getConversationDetail,
  refreshConversionInList,
  removeConversationFromList,
  updateConversationInfo,
  updateConversationModifiedTime,
} from "@/store/slices/conversationSlice";
import { useEffect, useMemo, useRef } from "react";

import { db } from "@/indexDB";
import { MessageStatus, TitleCreatedBy } from "@/interfaces";
import { buildUserContentBlocks, getMessageTextFromBlocks, ImageBlock } from "@/interfaces/contentBlock";
import {
  buildTempAssistantMessage,
  buildTempUserMessage,
  createLocalMessageId,
  getHistoryMessageIds,
  getRemovedMessageIds,
  isLocalMessageId,
  isTitleCreatedByUser,
  isUserRole,
  reportError,
  reportEvent,
} from "@/utils";
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
  deleteUserMessage: (messageId: string) => Promise<void>;
  reSendMessage: (index: number, message: ChatMessage, formData: ChatInputConfig) => Promise<void>;
  sendMessage: (values: ChatInputFormValues, options?: SendMessageOptions) => Promise<void>;
}

export const useChatState = (conversationId: string) => {
  return useAppSelector(state => state.chat[conversationId] || DEFAULT_CHAT_STATE);
};

interface TempMessageState {
  userTempId: string;
  assistantTempId: string;
  userServerMessageId?: string;
  assistantServerMessageId?: string;
}

export const useChatMessage = (options: UseChatMessageOptions) => {
  const { conversationId, historyLimit = 100 } = options;
  const dispatch = useAppDispatch();
  const { message } = App.useApp();
  const { messages, isLoading, isStreaming } = useChatState(conversationId);

  const abortControllerRef = useRef<AbortController | null>(null);
  const tempMessageRef = useRef<TempMessageState | null>(null);

  const resetState = useMemoizedFn(conversationId => {
    dispatch(resetChatState({ conversationId, data: undefined }));
  });

  const cleanupTempMessages = useMemoizedFn((conversationId: string, shouldDeleteRemoteMessages: boolean = false) => {
    const tempState = tempMessageRef.current;
    if (!tempState) {
      return;
    }

    const idsToRemove = [
      tempState.userTempId,
      tempState.assistantTempId,
      tempState.userServerMessageId,
      tempState.assistantServerMessageId,
    ].filter(Boolean) as string[];

    for (const messageId of new Set(idsToRemove)) {
      dispatch(removeMessageById({ conversationId, data: messageId }));
    }

    if (shouldDeleteRemoteMessages) {
      const remoteMessageIds = [tempState.userServerMessageId, tempState.assistantServerMessageId].filter(
        (messageId): messageId is string => Boolean(messageId) && !isLocalMessageId(messageId)
      );
      for (const messageId of new Set(remoteMessageIds)) {
        chatAPI.deleteMessage(messageId).catch(error => {
          reportError("cleanupTempMessages deleteMessage", {
            error,
            conversationId,
            messageId,
          });
        });
      }
    }

    tempMessageRef.current = null;
  });

  const abortMessage = useMemoizedFn((conversationId): void => {
    if (abortControllerRef.current && isStreaming) {
      abortControllerRef.current.abort();
      // isLoading 为 true 表示尚未收到首个内容事件，此时只应清理本轮临时消息。
      if (isLoading) {
        cleanupTempMessages(conversationId, true);
      }
      resetState(conversationId);
    }
  });

  const deleteMessage = useMemoizedFn(async (messageId: string): Promise<void> => {
    if (isStreaming) {
      return;
    }
    try {
      await chatAPI.deleteMessage(messageId);
      dispatch(removeMessageById({ conversationId, data: messageId }));
      message.success("已删除");
    } catch (error) {
      reportError("deleteMessage", { error, conversationId, messageId });
      message.error("删除失败");
    }
  });

  const sendMessage = useMemoizedFn(
    async (values: ChatInputFormValues, options?: SendMessageOptions): Promise<void> => {
      const { index, createdBy, attachmentBlocks } = options || {};
      const { content, ...requestConfig } = values;
      const normalizedValues: ChatInputFormValues = {
        ...values,
        content,
      };
      const userBlocks = buildUserContentBlocks(content, attachmentBlocks);
      if (userBlocks.length === 0) {
        return;
      }

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

        const userTempId = createLocalMessageId();
        const assistantTempId = createLocalMessageId();
        tempMessageRef.current = {
          userTempId,
          assistantTempId,
        };
        dispatch(
          addMessage({
            conversationId,
            data: buildTempUserMessage(userTempId, normalizedValues, userBlocks),
          })
        );
        dispatch(
          addMessage({
            conversationId,
            data: buildTempAssistantMessage(assistantTempId, userTempId, normalizedValues),
          })
        );

        // 流式传输消息处理器映射表
        const messageHandlers: StreamMessageHandlerMap = {
          // ack 后将临时消息替换为服务端消息
          ack: data => {
            const tempState = tempMessageRef.current;
            if (!tempState) {
              return;
            }
            if (isUserRole(data.role)) {
              tempState.userServerMessageId = data.id;
              dispatch(
                replaceMessageById({
                  conversationId,
                  messageId: tempState.userTempId,
                  data,
                })
              );
            } else {
              tempState.assistantServerMessageId = data.id;
              dispatch(
                replaceMessageById({
                  conversationId,
                  messageId: tempState.assistantTempId,
                  data,
                })
              );
            }
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

          content_block: data => {
            dispatch(
              appendContentBlockToLastMessage({
                conversationId,
                data,
              })
            );
          },

          // 本次消息流式传输结束
          done: data => {
            const { lastMessageUpdatedAt } = data;
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
            ...requestConfig,
            contentBlocks: userBlocks,
            historyIds, // 发送最后几条消息作为上下文
            regenerateTitle,
            removedMessageIds,
            conversationId,
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
            tempMessageRef.current = null;
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
        sendMessage(
          {
            ...formData,
            content: getMessageTextFromBlocks(message.contentBlocks),
          },
          {
            index,
            attachmentBlocks: message.contentBlocks.filter((b): b is ImageBlock => b.type === "image"),
          }
        );
      } else {
        // 如果是助手消息，则重新发送上一个用户消息
        const newIndex = index - 1;
        const userMessage = messages[newIndex];
        sendMessage(
          {
            ...formData,
            content: getMessageTextFromBlocks(userMessage.contentBlocks),
          },
          {
            index: newIndex,
            attachmentBlocks: userMessage.contentBlocks.filter((b): b is ImageBlock => b.type === "image"),
          }
        );
      }
    }
  );

  return {
    sendMessage,
    abortMessage,
    deleteMessage,
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
    // oxlint-disable-next-line react-hooks/exhaustive-deps
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
        attachmentBlocks: conversationState.attachmentBlocks,
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
