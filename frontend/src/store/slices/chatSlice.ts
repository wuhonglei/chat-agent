import { ChatConversationState, ChatMessage, MessageStatus, ToolCallMessage } from "@/interfaces";
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

export const getDefaultChatState = (): ChatConversationState => ({
  messages: [] as ChatMessage[],
  messageLoaded: false,
  lastMessageUpdateAt: "",
  isLoading: false,
  isStreaming: false,
  isReasoning: false,
  isCallingMcpTools: false,
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
      chatState.messages = data;
      chatState.messageLoaded = true;
      // lastMessageUpdateAt 的更新已移至 updateLastMessageTimeMiddleware 中自动处理
      // 数据库操作已移至 dbMiddleware 中处理，保持 reducer 的纯净性
    },
    // 首次刷新场景，此时 conversationInfo 还未获取，如果 indexDB 有数据，则设置临时消息
    setTempMessages: (state, action: PayloadAction<ConversationActionPayload<ChatMessage[]>>) => {
      const { conversationId, data } = action.payload;
      const chatState = conversationIdCheck(state, conversationId);
      chatState.messages = data;
    },
    addMessage: (state, action: PayloadAction<ConversationActionPayload<ChatMessage>>) => {
      const { conversationId, data } = action.payload;
      const chatState = conversationIdCheck(state, conversationId);
      chatState.messages.push(data);
      // lastMessageUpdateAt 的更新已移至 updateLastMessageTimeMiddleware 中自动处理
    },
    clearMessagesAfterIndex: (state, action: PayloadAction<ConversationActionPayload<number>>) => {
      const { conversationId, data: index } = action.payload;
      const chatState = conversationIdCheck(state, conversationId);
      // 清除该位置之后的所有消息
      chatState.messages.length = index + 1;
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
    setReasoning: (state, action: PayloadAction<ConversationActionPayload<boolean>>) => {
      const { conversationId, data } = action.payload;
      const chatState = conversationIdCheck(state, conversationId);
      chatState.isReasoning = data;
    },
    setCallingMcpTools: (state, action: PayloadAction<ConversationActionPayload<boolean>>) => {
      const { conversationId, data } = action.payload;
      const chatState = conversationIdCheck(state, conversationId);
      const lastMessage = lastMessageCheck(chatState.messages);
      if (lastMessage) {
        chatState.isCallingMcpTools = data;
      }
    },
    prependContentToLastMessage: (state, action: PayloadAction<ConversationActionPayload<string>>) => {
      const { conversationId, data } = action.payload;
      const chatState = conversationIdCheck(state, conversationId);
      const lastMessage = lastMessageCheck(chatState.messages);
      if (lastMessage) {
        lastMessage.content = data + lastMessage.content;
      }
    },
    appendContentToLastMessage: (state, action: PayloadAction<ConversationActionPayload<string>>) => {
      const { conversationId, data } = action.payload;
      const chatState = conversationIdCheck(state, conversationId);
      const lastMessage = lastMessageCheck(chatState.messages);
      if (lastMessage) {
        lastMessage.content += data;
      }
    },
    appendReasoningToLastMessage: (state, action: PayloadAction<ConversationActionPayload<string>>) => {
      const { conversationId, data } = action.payload;
      const chatState = conversationIdCheck(state, conversationId);
      const lastMessage = lastMessageCheck(chatState.messages);
      if (lastMessage) {
        lastMessage.reasoning += data;
      }
    },
    appendMcpToolCallToLastMessage: (state, action: PayloadAction<ConversationActionPayload<ToolCallMessage>>) => {
      const { conversationId, data } = action.payload;
      const chatState = conversationIdCheck(state, conversationId);
      const lastMessage = lastMessageCheck(chatState.messages);
      if (lastMessage) {
        lastMessage.toolCalls.push(data);
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
      chatState.isReasoning = false;
      chatState.isCallingMcpTools = false;
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
  clearMessagesAfterIndex,
  removeMessageById,
  setStreaming,
  setLoading,
  setCallingMcpTools,
  prependContentToLastMessage,
  appendContentToLastMessage,
  appendReasoningToLastMessage,
  appendMcpToolCallToLastMessage,
  setReasoning,
  updateMessageStatus,
  updateMessageModifiedTime,
  clearLastMessage,
  resetChatState,
  clearChatState,
} = chatSlice.actions;

export default chatSlice.reducer;
