import { MessageStatus } from "@/constants";
import { ChatMessage, SearchSource, ToolCallMessage } from "@/interfaces";
import { createSlice, PayloadAction } from "@reduxjs/toolkit";
import { isEmpty } from "lodash-es";

interface ChatState {
  messages: ChatMessage[];
  messageLoaded: boolean;
  lastMessageUpdateAt: string; // 等价于 messages.at(-1).createdAt
  isLoading: boolean;
  isStreaming: boolean;
  isReasoning: boolean;
  isCallingTools: boolean;
}

interface ChatStateMap {
  [conversionId: string]: ChatState;
}

// 修改 payload 接口，包含 conversationId
interface ConversationActionPayload<T = unknown> {
  conversationId: string;
  data: T;
}

export const getDefaultChatState = (): ChatState => ({
  messages: [],
  messageLoaded: false,
  lastMessageUpdateAt: "",
  isLoading: false,
  isStreaming: false,
  isReasoning: false,
  isCallingTools: false,
});

// 稳定的默认状态，避免每次创建新对象
export const DEFAULT_CHAT_STATE: ChatState = getDefaultChatState();

const conversationIdCheck = (
  state: ChatStateMap,
  conversionId: string
): ChatState => {
  if (!state[conversionId]) {
    state[conversionId] = getDefaultChatState();
  }
  return state[conversionId];
};

const initialState: ChatStateMap = {};

/**
 * 检查消息列表中最后一个消息是否为助手消息
 * @param messages
 * @returns
 */
export function lastMessageCheck(
  messages: ChatMessage[]
): ChatMessage | undefined {
  if (isEmpty(messages)) {
    return undefined;
  }

  return messages.at(-1)?.role === "assistant" ? messages.at(-1) : undefined;
}

const chatSlice = createSlice({
  name: "chat",
  initialState,
  reducers: {
    setMessages: (
      state,
      action: PayloadAction<ConversationActionPayload<ChatMessage[]>>
    ) => {
      const { conversationId, data } = action.payload;
      const chatState = conversationIdCheck(state, conversationId);
      chatState.messages = data;
      chatState.messageLoaded = true;
    },
    addMessage: (
      state,
      action: PayloadAction<ConversationActionPayload<ChatMessage>>
    ) => {
      const { conversationId, data } = action.payload;
      const chatState = conversationIdCheck(state, conversationId);
      chatState.messages.push(data);
    },
    clearMessagesAfterIndex: (
      state,
      action: PayloadAction<ConversationActionPayload<number>>
    ) => {
      const { conversationId, data: index } = action.payload;
      const chatState = conversationIdCheck(state, conversationId);
      // 清除该位置之后的所有消息
      chatState.messages.length = index + 1;
    },
    removeMessageById: (
      state,
      action: PayloadAction<ConversationActionPayload<string>>
    ) => {
      const { conversationId, data: messageId } = action.payload;
      const chatState = conversationIdCheck(state, conversationId);
      const index = chatState.messages.findIndex(
        message => message.id === messageId
      );
      if (index !== -1) {
        chatState.messages.splice(index, 1);
      }
    },
    clearLastMessage: (
      state,
      action: PayloadAction<ConversationActionPayload>
    ) => {
      const { conversationId } = action.payload;
      const chatState = conversationIdCheck(state, conversationId);
      const lastMessage = lastMessageCheck(chatState.messages);
      if (lastMessage) {
        chatState.messages.pop();
      }
    },
    setStreaming: (
      state,
      action: PayloadAction<ConversationActionPayload<boolean>>
    ) => {
      const { conversationId, data } = action.payload;
      const chatState = conversationIdCheck(state, conversationId);
      chatState.isStreaming = data;
    },
    setLoading: (
      state,
      action: PayloadAction<ConversationActionPayload<boolean>>
    ) => {
      const { conversationId, data } = action.payload;
      const chatState = conversationIdCheck(state, conversationId);
      chatState.isLoading = data;
    },
    setReasoning: (
      state,
      action: PayloadAction<ConversationActionPayload<boolean>>
    ) => {
      const { conversationId, data } = action.payload;
      const chatState = conversationIdCheck(state, conversationId);
      chatState.isReasoning = data;
    },
    setSources: (
      state,
      action: PayloadAction<ConversationActionPayload<SearchSource[]>>
    ) => {
      const { conversationId, data } = action.payload;
      const chatState = conversationIdCheck(state, conversationId);
      if (!isEmpty(chatState.messages)) {
        chatState.messages.at(-1)!.sources = data;
      }
    },
    setCallingTools: (
      state,
      action: PayloadAction<ConversationActionPayload<boolean>>
    ) => {
      const { conversationId, data } = action.payload;
      const chatState = conversationIdCheck(state, conversationId);
      const lastMessage = lastMessageCheck(chatState.messages);
      if (lastMessage) {
        chatState.isCallingTools = data;
      }
    },
    prependContentToLastMessage: (
      state,
      action: PayloadAction<ConversationActionPayload<string>>
    ) => {
      const { conversationId, data } = action.payload;
      const chatState = conversationIdCheck(state, conversationId);
      const lastMessage = lastMessageCheck(chatState.messages);
      if (lastMessage) {
        lastMessage.content = data + lastMessage.content;
      }
    },
    appendContentToLastMessage: (
      state,
      action: PayloadAction<ConversationActionPayload<string>>
    ) => {
      const { conversationId, data } = action.payload;
      const chatState = conversationIdCheck(state, conversationId);
      const lastMessage = lastMessageCheck(chatState.messages);
      if (lastMessage) {
        lastMessage.content += data;
      }
    },
    prependSourceToLastReasoningMessage: (
      state,
      action: PayloadAction<ConversationActionPayload<string>>
    ) => {
      const { conversationId, data } = action.payload;
      const chatState = conversationIdCheck(state, conversationId);
      const lastMessage = lastMessageCheck(chatState.messages);
      if (lastMessage && lastMessage.messageMetadata.thinkMode) {
        lastMessage.reasoning = data + lastMessage.reasoning;
      }
    },
    appendReasoningToLastMessage: (
      state,
      action: PayloadAction<ConversationActionPayload<string>>
    ) => {
      const { conversationId, data } = action.payload;
      const chatState = conversationIdCheck(state, conversationId);
      const lastMessage = lastMessageCheck(chatState.messages);
      if (lastMessage) {
        lastMessage.reasoning += data;
      }
    },
    appendToolCallToLastMessage: (
      state,
      action: PayloadAction<ConversationActionPayload<ToolCallMessage>>
    ) => {
      const { conversationId, data } = action.payload;
      const chatState = conversationIdCheck(state, conversationId);
      const lastMessage = lastMessageCheck(chatState.messages);
      if (lastMessage) {
        lastMessage.toolCalls.push(data);
      }
    },
    updateMessageStatus: (
      state,
      action: PayloadAction<ConversationActionPayload<MessageStatus>>
    ) => {
      const { conversationId, data } = action.payload;
      const chatState = conversationIdCheck(state, conversationId);
      const lastMessage = lastMessageCheck(chatState.messages);
      if (lastMessage) {
        lastMessage.status = data;
      }
    },
    updateMessageModifiedTime: (
      state,
      action: PayloadAction<ConversationActionPayload<string>>
    ) => {
      const { conversationId, data } = action.payload;
      const chatState = conversationIdCheck(state, conversationId);
      chatState.lastMessageUpdateAt = data;
    },
    // 会话中 message finish 时调用
    resetChatState: (
      state,
      action: PayloadAction<ConversationActionPayload>
    ) => {
      const { conversationId } = action.payload;
      const chatState = conversationIdCheck(state, conversationId);
      chatState.isLoading = false;
      chatState.isStreaming = false;
      chatState.isReasoning = false;
      chatState.isCallingTools = false;
    },
    // 删除会话时调用
    clearChatState: (
      state,
      action: PayloadAction<ConversationActionPayload>
    ) => {
      const { conversationId } = action.payload;
      delete state[conversationId];
    },
  },
});

export const {
  setMessages,
  addMessage,
  clearMessagesAfterIndex,
  removeMessageById,
  setStreaming,
  setLoading,
  setSources,
  setCallingTools,
  prependContentToLastMessage,
  appendContentToLastMessage,
  prependSourceToLastReasoningMessage,
  appendReasoningToLastMessage,
  appendToolCallToLastMessage,
  setReasoning,
  updateMessageStatus,
  updateMessageModifiedTime,
  clearLastMessage,
  resetChatState,
  clearChatState,
} = chatSlice.actions;

export default chatSlice.reducer;
