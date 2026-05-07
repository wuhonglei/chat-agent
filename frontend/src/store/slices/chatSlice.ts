import {
  ChatConversationState,
  ChatMessage,
  ContentBlock,
  ContentBlockEvent,
  MessageStatus,
  StreamResumeContext,
  StreamResumePhase,
} from "@/interfaces";
import { createSlice, PayloadAction } from "@reduxjs/toolkit";
import { isEmpty } from "lodash-es";

interface ChatStateMap {
  [conversionId: string]: ChatConversationState;
}

// 修改 payload 接口，包含 conversationId
interface ConversationActionPayload<T = unknown> {
  conversationId: string;
  data: T;
}

interface ReplaceMessagePayload {
  conversationId: string;
  messageId: string;
  data: ChatMessage;
}

interface StreamResumeContextPayload {
  conversationId: string;
  data: StreamResumeContext;
}

export const getDefaultChatState = (): ChatConversationState => ({
  messages: [] as ChatMessage[],
  messageLoaded: false,
  lastMessageUpdateAt: "",
  isLoading: false,
  isStreaming: false,
  streamResumeContext: null,
});

// 稳定的默认状态，避免每次创建新对象
export const DEFAULT_CHAT_STATE: ChatConversationState = getDefaultChatState();

const conversationIdCheck = (state: ChatStateMap, conversionId: string): ChatConversationState => {
  if (!state[conversionId]) {
    state[conversionId] = getDefaultChatState();
  }
  return state[conversionId];
};

const initialState: ChatStateMap = {};

function normalizeMessage(message: ChatMessage): ChatMessage {
  return {
    ...message,
    contentBlocks: message.contentBlocks || [],
  };
}

/**
 * 检查消息列表中最后一个消息是否为助手消息
 * @param messages
 * @returns
 */
export function lastMessageCheck(messages: ChatMessage[]): ChatMessage | undefined {
  if (isEmpty(messages)) {
    return undefined;
  }

  const lastMessage = messages.at(-1);
  return lastMessage?.role === "assistant" ? lastMessage : undefined;
}

// 注意：lastMessageUpdateAt 的更新已移至 updateLastMessageTimeMiddleware 中自动处理

const chatSlice = createSlice({
  name: "chat",
  initialState,
  reducers: {
    setMessages: (state, action: PayloadAction<ConversationActionPayload<ChatMessage[]>>) => {
      const { conversationId, data } = action.payload;
      const chatState = conversationIdCheck(state, conversationId);
      chatState.messages = data.map(normalizeMessage);
      chatState.messageLoaded = true;
      // lastMessageUpdateAt 的更新已移至 updateLastMessageTimeMiddleware 中自动处理
      // 数据库操作已移至 dbMiddleware 中处理，保持 reducer 的纯净性
    },
    // 首次刷新场景，此时 conversationInfo 还未获取，如果 indexDB 有数据，则设置临时消息
    setTempMessages: (state, action: PayloadAction<ConversationActionPayload<ChatMessage[]>>) => {
      const { conversationId, data } = action.payload;
      const chatState = conversationIdCheck(state, conversationId);
      chatState.messages = data.map(normalizeMessage);
    },
    addMessage: (state, action: PayloadAction<ConversationActionPayload<ChatMessage>>) => {
      const { conversationId, data } = action.payload;
      const chatState = conversationIdCheck(state, conversationId);
      chatState.messages.push(normalizeMessage(data));
      // lastMessageUpdateAt 的更新已移至 updateLastMessageTimeMiddleware 中自动处理
    },
    replaceMessageById: (state, action: PayloadAction<ReplaceMessagePayload>) => {
      const { conversationId, messageId, data } = action.payload;
      const chatState = conversationIdCheck(state, conversationId);
      const index = chatState.messages.findIndex(message => message.id === messageId);
      if (index !== -1) {
        chatState.messages[index] = normalizeMessage(data);
      }
    },
    clearMessagesAfterIndex: (state, action: PayloadAction<ConversationActionPayload<number>>) => {
      const { conversationId, data: index } = action.payload;
      const chatState = conversationIdCheck(state, conversationId);
      // 清除该位置之后的所有消息
      chatState.messages.length = index;
      // lastMessageUpdateAt 的更新已移至 updateLastMessageTimeMiddleware 中自动处理
    },
    removeMessageById: (state, action: PayloadAction<ConversationActionPayload<string>>) => {
      const { conversationId, data: messageId } = action.payload;
      const chatState = conversationIdCheck(state, conversationId);
      const index = chatState.messages.findIndex(message => message.id === messageId);
      if (index !== -1) {
        chatState.messages.splice(index, 1);
        // lastMessageUpdateAt 的更新已移至 updateLastMessageTimeMiddleware 中自动处理
      }
    },
    clearLastMessage: (state, action: PayloadAction<ConversationActionPayload>) => {
      const { conversationId } = action.payload;
      const chatState = conversationIdCheck(state, conversationId);
      const lastMessage = lastMessageCheck(chatState.messages);
      if (lastMessage) {
        chatState.messages.pop();
        // lastMessageUpdateAt 的更新已移至 updateLastMessageTimeMiddleware 中自动处理
      }
    },
    setStreaming: (state, action: PayloadAction<ConversationActionPayload<boolean>>) => {
      const { conversationId, data } = action.payload;
      const chatState = conversationIdCheck(state, conversationId);
      chatState.isStreaming = data;
    },
    setLoading: (state, action: PayloadAction<ConversationActionPayload<boolean>>) => {
      const { conversationId, data } = action.payload;
      const chatState = conversationIdCheck(state, conversationId);
      chatState.isLoading = data;
    },
    prependContentToLastMessage: (state, action: PayloadAction<ConversationActionPayload<string>>) => {
      const { conversationId, data } = action.payload;
      const chatState = conversationIdCheck(state, conversationId);
      const lastMessage = lastMessageCheck(chatState.messages);
      if (lastMessage) {
        const firstTextBlock = lastMessage.contentBlocks.find(block => block.type === "text");
        if (firstTextBlock && firstTextBlock.type === "text") {
          firstTextBlock.text = data + firstTextBlock.text;
        } else {
          lastMessage.contentBlocks.unshift({
            id: `legacy_text_${Date.now()}`,
            type: "text",
            text: data,
          });
        }
      }
    },
    appendContentToLastMessage: (state, action: PayloadAction<ConversationActionPayload<string>>) => {
      const { conversationId, data } = action.payload;
      const chatState = conversationIdCheck(state, conversationId);
      const lastMessage = lastMessageCheck(chatState.messages);
      if (lastMessage) {
        const textBlocks = lastMessage.contentBlocks.filter(block => block.type === "text");
        const lastTextBlock = textBlocks.at(-1);
        if (lastTextBlock && lastTextBlock.type === "text") {
          lastTextBlock.text += data;
        } else {
          lastMessage.contentBlocks.push({
            id: `legacy_text_${Date.now()}`,
            type: "text",
            text: data,
          });
        }
      }
    },
    appendReasoningToLastMessage: (state, action: PayloadAction<ConversationActionPayload<string>>) => {
      const { conversationId, data } = action.payload;
      const chatState = conversationIdCheck(state, conversationId);
      const lastMessage = lastMessageCheck(chatState.messages);
      if (lastMessage) {
        const block: ContentBlock = {
          id: `legacy_reasoning_${Date.now()}`,
          type: "thinking",
          text: data,
        };
        lastMessage.contentBlocks.push(block);
      }
    },
    appendContentBlockToLastMessage: (state, action: PayloadAction<ConversationActionPayload<ContentBlockEvent>>) => {
      const { conversationId, data } = action.payload;
      const chatState = conversationIdCheck(state, conversationId);
      const lastMessage = lastMessageCheck(chatState.messages);
      if (!lastMessage) {
        return;
      }
      if (data.op === "append") {
        lastMessage.contentBlocks.push(data.block);
        return;
      }
      if (data.op === "delta") {
        const target = lastMessage.contentBlocks.find(block => block.id === data.blockId);
        if (target && (target.type === "text" || target.type === "thinking")) {
          target.text += data.delta;
        }
        return;
      }
      if (data.op === "tool_delta") {
        const target = lastMessage.contentBlocks.find(block => block.id === data.blockId);
        if (target && target.type === "tool_use") {
          target.argumentsText += data.argumentsDelta || "";
          if (data.name) {
            target.name = data.name;
          }
          if (data.toolCallId) {
            target.toolCallId = data.toolCallId;
          }
        }
        return;
      }
      if (data.op === "finalize_round") {
        for (const block of lastMessage.contentBlocks) {
          if (block.type !== "tool_use") {
            continue;
          }
          if (block.argumentsJson !== null) {
            continue;
          }
          try {
            block.argumentsJson = block.argumentsText
              ? (JSON.parse(block.argumentsText) as Record<string, unknown>)
              : {};
          } catch {
            block.argumentsJson = undefined;
          }
        }
      }
    },
    updateMessageStatus: (state, action: PayloadAction<ConversationActionPayload<MessageStatus>>) => {
      const { conversationId, data } = action.payload;
      const chatState = conversationIdCheck(state, conversationId);
      const lastMessage = lastMessageCheck(chatState.messages);
      if (lastMessage) {
        lastMessage.status = data;
      }
    },
    updateMessageModifiedTime: (state, action: PayloadAction<ConversationActionPayload<string>>) => {
      const { conversationId, data } = action.payload;
      const chatState = conversationIdCheck(state, conversationId);
      chatState.lastMessageUpdateAt = data;
    },
    // 会话中 message finish 时调用
    resetChatState: (state, action: PayloadAction<ConversationActionPayload>) => {
      const { conversationId } = action.payload;
      const chatState = conversationIdCheck(state, conversationId);
      chatState.isLoading = false;
      chatState.isStreaming = false;
      chatState.streamResumeContext = null;
    },
    setStreamResumeContext: (state, action: PayloadAction<StreamResumeContextPayload>) => {
      const { conversationId, data } = action.payload;
      const chatState = conversationIdCheck(state, conversationId);
      chatState.streamResumeContext = data;
    },
    updateStreamResumeSeq: (state, action: PayloadAction<ConversationActionPayload<number>>) => {
      const { conversationId, data } = action.payload;
      const chatState = conversationIdCheck(state, conversationId);
      if (!chatState.streamResumeContext) {
        return;
      }
      if (data <= chatState.streamResumeContext.lastSeq) {
        return;
      }
      chatState.streamResumeContext.lastSeq = data;
      chatState.streamResumeContext.updatedAt = new Date().toISOString();
    },
    updateStreamResumePhase: (state, action: PayloadAction<ConversationActionPayload<StreamResumePhase>>) => {
      const { conversationId, data } = action.payload;
      const chatState = conversationIdCheck(state, conversationId);
      if (!chatState.streamResumeContext) {
        return;
      }
      chatState.streamResumeContext.phase = data;
      chatState.streamResumeContext.updatedAt = new Date().toISOString();
    },
    clearStreamResumeContext: (state, action: PayloadAction<ConversationActionPayload>) => {
      const { conversationId } = action.payload;
      const chatState = conversationIdCheck(state, conversationId);
      chatState.streamResumeContext = null;
    },
    // 删除会话时调用
    clearChatState: (state, action: PayloadAction<ConversationActionPayload>) => {
      const { conversationId } = action.payload;
      delete state[conversationId];
    },
  },
});

export const {
  setMessages,
  setTempMessages,
  addMessage,
  replaceMessageById,
  clearMessagesAfterIndex,
  removeMessageById,
  setStreaming,
  setLoading,
  prependContentToLastMessage,
  appendContentToLastMessage,
  appendReasoningToLastMessage,
  appendContentBlockToLastMessage,
  updateMessageStatus,
  updateMessageModifiedTime,
  clearLastMessage,
  resetChatState,
  setStreamResumeContext,
  updateStreamResumeSeq,
  updateStreamResumePhase,
  clearStreamResumeContext,
  clearChatState,
} = chatSlice.actions;

export default chatSlice.reducer;
