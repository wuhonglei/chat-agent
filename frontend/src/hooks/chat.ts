import {
  ChatInputConfig,
  ChatInputFormValues,
  ChatMessage,
  ConversationInfo,
  NewConversationCache,
  SendMessageOptions,
  StreamMessage,
  StreamResumeContext,
} from "@/interfaces";
import { chatAPI } from "@/services";
import { useAppDispatch, useAppSelector } from "@/store/hooks";
import {
  addMessage,
  appendContentBlockToLastMessage,
  clearLastMessage,
  clearMessagesAfterIndex,
  clearStreamResumeContext,
  DEFAULT_CHAT_STATE,
  lastMessageCheck,
  removeMessageById,
  replaceMessageById,
  resetChatState,
  setLoading,
  setMessages,
  setStreaming,
  setStreamResumeContext,
  setTempMessages,
  updateMessageModifiedTime,
  updateMessageStatus,
  updateStreamResumePhase,
  updateStreamResumeSeq,
} from "@/store/slices/chatSlice";
import {
  getConversationDetail,
  refreshConversionInList,
  removeConversationFromList,
  updateConversationInfo,
  updateConversationModifiedTime,
} from "@/store/slices/conversationSlice";
import { useEffect, useMemo, useRef, type RefObject } from "react";

import { db } from "@/indexDB";
import { MessageFeedbackValue, MessageStatus, TitleCreatedBy } from "@/interfaces";
import { buildUserContentBlocks, getMessageTextFromBlocks, isUserAttachmentBlock } from "@/interfaces/contentBlock";
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
  withDevConversationTitlePrefix,
} from "@/utils";
import { useMemoizedFn, useRequest } from "ahooks";
import { App } from "antd";
import dayjs from "dayjs";
import { isEmpty, isNumber } from "lodash-es";
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
  updateMessageFeedback: (messageId: string, value: MessageFeedbackValue) => Promise<void>;
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

interface UseAutoResumeParams {
  conversationId: string;
  streamResumeContext: StreamResumeContext | null;
  messagesLength: number;
  isStreaming: boolean;
  abortControllerRef: RefObject<AbortController | null>;
  autoResumeAttemptedRef: RefObject<string | null>;
  handleStreamPayload: (
    payload: StreamMessage,
    mode: "initial" | "resume",
    onDone?: (data: Extract<StreamMessage, { type: "done" }>["data"]) => void,
    onProtocolError?: (error: Error) => void
  ) => void;
  resetState: (conversationId: string) => void;
  dispatch: ReturnType<typeof useAppDispatch>;
}

const autoResumeInFlightKeys = new Set<string>();

const useAutoResume = ({
  conversationId,
  streamResumeContext,
  messagesLength,
  isStreaming,
  abortControllerRef,
  autoResumeAttemptedRef,
  handleStreamPayload,
  resetState,
  dispatch,
}: UseAutoResumeParams): void => {
  const resumeAssistantMessageId = streamResumeContext?.assistantMessageId;
  const resumePhase = streamResumeContext?.phase;
  const resumeStartSeq = streamResumeContext?.lastSeq ?? 0;

  useEffect(() => {
    if (!resumeAssistantMessageId) {
      return;
    }
    if (resumePhase === "done") {
      return;
    }
    if (messagesLength === 0) {
      return;
    }
    if (isStreaming) {
      return;
    }
    const attemptKey = `${resumeAssistantMessageId}`;
    if (autoResumeAttemptedRef.current === attemptKey) {
      return;
    }
    const inFlightKey = `${conversationId}:${attemptKey}`;
    if (autoResumeInFlightKeys.has(inFlightKey)) {
      return;
    }
    autoResumeInFlightKeys.add(inFlightKey);
    autoResumeAttemptedRef.current = attemptKey;

    let cancelled = false;
    let cleanedCurrentController = false;
    const controller = new AbortController();
    abortControllerRef.current = controller;
    console.info("useChatMessage autoResume", conversationId);
    dispatch(setStreaming({ conversationId, data: true }));
    dispatch(setLoading({ conversationId, data: true }));

    const handleResume = async (): Promise<void> => {
      let streamDone = false;
      let streamError: Error | null = null;
      try {
        await chatAPI.streamMessageResume(
          {
            assistantMessageId: resumeAssistantMessageId,
            lastSeq: resumeStartSeq,
          },
          (payload: StreamMessage) => {
            handleStreamPayload(
              payload,
              "resume",
              () => {
                streamDone = true;
                resetState(conversationId);
              },
              error => {
                streamError = error;
              }
            );
          },
          (error: Error) => {
            streamError = error;
            dispatch(updateStreamResumePhase({ conversationId, data: "error" }));
          },
          () => {},
          controller
        );

        if (!streamDone && !streamError && !controller.signal.aborted) {
          dispatch(updateStreamResumePhase({ conversationId, data: "closed" }));
        }
      } catch (error) {
        if (!cancelled && !controller.signal.aborted) {
          dispatch(updateStreamResumePhase({ conversationId, data: "error" }));
          reportError("autoResume stream failed", { error, conversationId });
        }
      } finally {
        const isCurrentController = abortControllerRef.current === controller;
        if (!streamDone && (isCurrentController || cleanedCurrentController)) {
          dispatch(setStreaming({ conversationId, data: false }));
          dispatch(setLoading({ conversationId, data: false }));
        }
        autoResumeInFlightKeys.delete(inFlightKey);
      }
    };

    handleResume();
    return () => {
      cancelled = true;
      if (abortControllerRef.current === controller) {
        abortControllerRef.current = null;
        cleanedCurrentController = true;
      }
      controller.abort();
    };
  }, [
    abortControllerRef,
    autoResumeAttemptedRef,
    conversationId,
    dispatch,
    handleStreamPayload,
    messagesLength,
    resetState,
    resumeAssistantMessageId,
  ]);
};

const buildStreamResumeContextFromMessages = (messages: ChatMessage[]): StreamResumeContext | null => {
  const resumableAssistantMessage = [...messages]
    .reverse()
    .find(item => item.role === "assistant" && item.status === MessageStatus.Pending && !isLocalMessageId(item.id));

  if (!resumableAssistantMessage) {
    return null;
  }

  return {
    assistantMessageId: resumableAssistantMessage.id,
    // 从服务端拉取后的重建场景，无法得知精确 seq，先从 0 开始续传。
    lastSeq: 0,
    phase: "closed",
    updatedAt: new Date().toISOString(),
  };
};

export const useChatMessage = (options: UseChatMessageOptions) => {
  const { conversationId, historyLimit = 100 } = options;
  const dispatch = useAppDispatch();
  const { message } = App.useApp();
  const { messages, isLoading, isStreaming, streamResumeContext } = useChatState(conversationId);

  const abortControllerRef = useRef<AbortController | null>(null);
  const tempMessageRef = useRef<TempMessageState | null>(null);
  const streamLastSeqRef = useRef<number>(0);
  const autoResumeAttemptedRef = useRef<string | null>(null);

  useEffect(() => {
    if (!streamResumeContext) {
      return;
    }
    streamLastSeqRef.current = streamResumeContext.lastSeq;
    if (tempMessageRef.current && !tempMessageRef.current.assistantServerMessageId) {
      tempMessageRef.current.assistantServerMessageId = streamResumeContext.assistantMessageId;
    }
  }, [streamResumeContext]);

  const resetState = useMemoizedFn(conversationId => {
    tempMessageRef.current = null;
    streamLastSeqRef.current = 0;
    autoResumeAttemptedRef.current = null;
    dispatch(resetChatState({ conversationId, data: undefined }));
  });

  const abortMessage = useMemoizedFn((conversationId): void => {
    if (abortControllerRef.current && isStreaming) {
      abortControllerRef.current.abort();
      const lastMessage = lastMessageCheck(messages);
      if (lastMessage && lastMessage.id && isLoading) {
        dispatch(clearLastMessage({ conversationId, data: undefined }));
        if (!isLocalMessageId(lastMessage.id)) {
          chatAPI.deleteMessage(lastMessage.id).catch(error => {
            reportError("abortMessage deleteMessage", {
              error,
              conversationId,
              messageId: lastMessage.id,
            });
          });
        }
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

  const updateMessageFeedback = useMemoizedFn(async (messageId: string, value: MessageFeedbackValue): Promise<void> => {
    if (isStreaming) {
      return;
    }
    try {
      const updatedFeedback = await chatAPI.updateMessageFeedback(messageId, value);
      const targetMessage = messages.find(item => item.id === messageId);
      if (!targetMessage) {
        return;
      }
      dispatch(
        replaceMessageById({
          conversationId,
          messageId,
          data: {
            ...targetMessage,
            feedback: updatedFeedback,
          },
        })
      );
      dispatch(
        updateConversationModifiedTime({
          conversationId,
          lastMessageUpdatedAt: updatedFeedback.updatedAt,
        })
      );
    } catch (error) {
      reportError("updateMessageFeedback", {
        error,
        conversationId,
        messageId,
        value,
      });
      message.error("反馈更新失败");
    }
  });

  const handleStreamPayload = useMemoizedFn(
    (
      payload: StreamMessage,
      mode: "initial" | "resume",
      onDone?: (data: Extract<StreamMessage, { type: "done" }>["data"]) => void,
      onProtocolError?: (error: Error) => void
    ): void => {
      if (isNumber(payload.seq) && payload.seq > streamLastSeqRef.current) {
        streamLastSeqRef.current = payload.seq;
        dispatch(updateStreamResumeSeq({ conversationId, data: payload.seq }));
      }

      const { type, data } = payload;
      if (!["ack", "refresh_conversation", "title"].includes(type)) {
        dispatch(setLoading({ conversationId, data: false }));
      }

      if (type === "refresh_conversation") {
        dispatch(refreshConversionInList(data as ConversationInfo));
        return;
      }
      if (type === "title") {
        const { id, title } = data;
        dispatch(
          updateConversationInfo({
            id,
            title: withDevConversationTitlePrefix(title),
            createdBy: TitleCreatedBy.LLM,
          })
        );
        return;
      }

      if (type === "ack") {
        if (mode === "initial") {
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
              setStreamResumeContext({
                conversationId,
                data: {
                  assistantMessageId: data.id,
                  lastSeq: streamLastSeqRef.current,
                  phase: "streaming",
                  updatedAt: new Date().toISOString(),
                },
              })
            );
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
          return;
        }

        if (!isUserRole(data.role)) {
          dispatch(
            replaceMessageById({
              conversationId,
              messageId: data.id,
              data,
            })
          );
          dispatch(
            updateMessageModifiedTime({
              conversationId,
              data: data.updatedAt,
            })
          );
        }
        return;
      }

      if (type === "content_block") {
        dispatch(appendContentBlockToLastMessage({ conversationId, data }));
        return;
      }

      if (type === "done") {
        dispatch(updateStreamResumePhase({ conversationId, data: "done" }));
        dispatch(updateMessageStatus({ conversationId, data: MessageStatus.Done }));
        dispatch(
          updateMessageModifiedTime({
            conversationId,
            data: data.lastMessageUpdatedAt,
          })
        );
        dispatch(
          updateConversationModifiedTime({
            conversationId,
            lastMessageUpdatedAt: data.lastMessageUpdatedAt,
          })
        );
        onDone?.(data);
        return;
      }

      if (type === "error") {
        const { content } = data || {};
        if (content) {
          message.error(content);
        }
        dispatch(updateStreamResumePhase({ conversationId, data: "error" }));
        reportError("Stream Error", { error: data, conversationId, mode });
        onProtocolError?.(new Error(content || "Stream error"));
        return;
      }

      console.warn(`Unknown message type: ${type}`);
      reportError("streamMessage onMessage Unknown Message Type", {
        type,
        conversationId,
      });
    }
  );

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
        const abortController = new AbortController();
        abortControllerRef.current = abortController;
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

        const maxResumeRetries = 3;
        let streamDone = false;
        let streamError: Error | null = null;

        const handleInitialStreamMessage = (data: StreamMessage): void => {
          handleStreamPayload(
            data,
            "initial",
            doneData => {
              streamDone = true;
              resetState(conversationId);
              reportEvent("message_stream_done", doneData);
            },
            error => {
              streamError = error;
            }
          );
        };
        const handleResumeStreamMessage = (data: StreamMessage): void => {
          handleStreamPayload(
            data,
            "resume",
            doneData => {
              streamDone = true;
              resetState(conversationId);
              reportEvent("message_stream_done", doneData);
            },
            error => {
              streamError = error;
            }
          );
        };

        const handleStreamError = (error: Error): void => {
          streamError = error;
          dispatch(updateStreamResumePhase({ conversationId, data: "error" }));
          reportError("streamMessage onError", {
            error,
            conversationId,
          });
        };

        for (let attempt = 0; attempt <= maxResumeRetries; attempt++) {
          streamError = null;
          const isResumeAttempt = attempt > 0;
          const tempState = tempMessageRef.current;
          const assistantMessageId = tempState?.assistantServerMessageId || streamResumeContext?.assistantMessageId;

          if (isResumeAttempt && !assistantMessageId) {
            throw new Error("Resume skipped: assistant message id is missing");
          }

          if (isResumeAttempt) {
            await chatAPI.streamMessageResume(
              {
                assistantMessageId: assistantMessageId!,
                lastSeq: streamLastSeqRef.current,
              },
              handleResumeStreamMessage,
              handleStreamError,
              () => {},
              abortController
            );
          } else {
            await chatAPI.streamMessage(
              {
                ...requestConfig,
                contentBlocks: userBlocks,
                historyIds, // 发送最后几条消息作为上下文
                regenerateTitle,
                removedMessageIds,
                conversationId,
              },
              handleInitialStreamMessage,
              handleStreamError,
              () => {},
              abortController
            );
            console.info("await chatAPI.streamMessage");
          }

          if (streamDone || abortController.signal.aborted) {
            break;
          }
          if (!streamError && !isResumeAttempt) {
            // 首次流在无 done 的情况下关闭，尝试走一次 resume（例如网络抖动）
            dispatch(updateStreamResumePhase({ conversationId, data: "closed" }));
            continue;
          }
          if (!streamError && isResumeAttempt) {
            dispatch(updateStreamResumePhase({ conversationId, data: "closed" }));
            break;
          }
          if (attempt === maxResumeRetries) {
            throw streamError;
          }
          await new Promise(resolve => setTimeout(resolve, 500 * (attempt + 1)));
        }

        if (!streamDone && !abortController.signal.aborted) {
          resetState(conversationId);
        }
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
            attachmentBlocks: message.contentBlocks.filter(isUserAttachmentBlock),
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
            attachmentBlocks: userMessage.contentBlocks.filter(isUserAttachmentBlock),
          }
        );
      }
    }
  );

  useAutoResume({
    conversationId,
    streamResumeContext,
    messagesLength: messages.length,
    isStreaming,
    abortControllerRef,
    autoResumeAttemptedRef,
    handleStreamPayload,
    resetState,
    dispatch,
  });

  return {
    sendMessage,
    abortMessage,
    deleteMessage,
    reSendMessage,
    updateMessageFeedback,
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
        const rebuiltStreamResumeContext = buildStreamResumeContextFromMessages(data);
        if (rebuiltStreamResumeContext) {
          dispatch(
            setStreamResumeContext({
              conversationId,
              data: rebuiltStreamResumeContext,
            })
          );
          return;
        }
        dispatch(clearStreamResumeContext({ conversationId, data: undefined }));
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
        const cachedChatState = data?.data;
        // 首次刷新时，conversationInfo 还未获取到，则不加载消息
        if (!lastMessageUpdateAt) {
          if (!isEmpty(cachedChatState?.messages)) {
            dispatch(
              setTempMessages({
                conversationId,
                data: cachedChatState?.messages as ChatMessage[],
              })
            );
            if (cachedChatState?.streamResumeContext) {
              dispatch(
                setStreamResumeContext({
                  conversationId,
                  data: cachedChatState.streamResumeContext,
                })
              );
            } else {
              dispatch(clearStreamResumeContext({ conversationId, data: undefined }));
            }
            console.info("use temp messages from indexDB", conversationId);
          } else {
            console.info("conversationInfo not loaded yet, will load messages later", conversationId);
          }
          return;
        }

        // indexDB 中没有数据，则加载消息
        if (!cachedChatState || !cachedChatState.lastMessageUpdateAt) {
          loadMessages(conversationId);
          return;
        }

        // indexDB 中的数据比较旧，则加载消息
        const {
          messages,
          lastMessageUpdateAt: cacheLastMessageUpdateAt,
          streamResumeContext: cachedResumeContext,
        } = cachedChatState;
        console.info("cacheLastMessageUpdateAt", cacheLastMessageUpdateAt);
        console.info("lastMessageUpdateAt", lastMessageUpdateAt);
        if (dayjs(cacheLastMessageUpdateAt).isBefore(dayjs(lastMessageUpdateAt))) {
          loadMessages(conversationId);
          return;
        }

        // indexDB 中的数据比较新，则直接使用 indexDB 中的数据
        dispatch(setMessages({ conversationId, data: messages }));
        if (cachedResumeContext) {
          dispatch(
            setStreamResumeContext({
              conversationId,
              data: cachedResumeContext,
            })
          );
        } else {
          dispatch(clearStreamResumeContext({ conversationId, data: undefined }));
        }
        console.info("use cached data", conversationId);
      })
      .catch(error => {
        console.info("error getting messages from indexedDB", error);
        loadMessages(conversationId);
      });
  }, [isNewConversation, conversationId, messageLoaded, lastMessageUpdateAt, dispatch, loadMessages]);
};
