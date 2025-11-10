import { MessageStatus } from "@/constants";
import { ChatMessage, SearchSource, ToolCallMessage } from "@/interfaces";
import { createSlice, PayloadAction } from "@reduxjs/toolkit";
import { isEmpty } from "lodash-es";

interface ChatState {
  messages: ChatMessage[];
  messageLoaded: boolean;
  lastMessageCreatedAt: string; // 等价于 messages.at(-1).createdAt
  isLoading: boolean;
  isStreaming: boolean;
  isReasoning: boolean;
  isCallingTools: boolean;
}

interface ChatStateMap {
  [conversionId: string]: ChatState;
}

export const getDefaultChatState = (): ChatState => ({
  messages: [],
  messageLoaded: false,
  lastMessageCreatedAt: "",
  isLoading: false,
  isStreaming: false,
  isReasoning: false,
  isCallingTools: false,
});

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
      action: PayloadAction<{ conversionId: string; messages: ChatMessage[] }>
    ) => {
      const chatState = conversationIdCheck(state, action.payload.conversionId);
      chatState.messages = action.payload.messages;
    },
    addMessage: (
      state,
      action: PayloadAction<{ conversionId: string; message: ChatMessage }>
    ) => {
      const chatState = conversationIdCheck(state, action.payload.conversionId);
      chatState.messages.push(action.payload.message);
    },
    addMessageAtIndex: (
      state,
      action: PayloadAction<{
        conversionId: string;
        message: ChatMessage;
        index: number;
      }>
    ) => {
      // 插入到指定位置
      const chatState = conversationIdCheck(state, action.payload.conversionId);
      chatState.messages.splice(
        action.payload.index,
        0,
        action.payload.message
      );
      // 清除该位置之后的所有消息
      chatState.messages.length = action.payload.index + 1;
    },
    removeMessageById: (
      state,
      action: PayloadAction<{ conversionId: string; messageId: string }>
    ) => {
      const chatState = conversationIdCheck(state, action.payload.conversionId);
      const index = chatState.messages.findIndex(
        message => message.id === action.payload.messageId
      );
      if (index !== -1) {
        chatState.messages.splice(index, 1);
      }
    },
    clearLastMessage: (
      state,
      action: PayloadAction<{ conversionId: string }>
    ) => {
      const chatState = conversationIdCheck(state, action.payload.conversionId);
      const lastMessage = lastMessageCheck(chatState.messages);
      if (lastMessage) {
        chatState.messages.pop();
      }
    },
    clearMessages: (state, action: PayloadAction<{ conversionId: string }>) => {
      const chatState = conversationIdCheck(state, action.payload.conversionId);
      chatState.messages = [];
    },
    setStreaming: (
      state,
      action: PayloadAction<{ conversionId: string; isStreaming: boolean }>
    ) => {
      const chatState = conversationIdCheck(state, action.payload.conversionId);
      chatState.isStreaming = action.payload.isStreaming;
    },
    setLoading: (
      state,
      action: PayloadAction<{ conversionId: string; isLoading: boolean }>
    ) => {
      const chatState = conversationIdCheck(state, action.payload.conversionId);
      chatState.isLoading = action.payload.isLoading;
    },
    setReasoning: (
      state,
      action: PayloadAction<{ conversionId: string; isReasoning: boolean }>
    ) => {
      const chatState = conversationIdCheck(state, action.payload.conversionId);
      chatState.isReasoning = action.payload.isReasoning;
    },
    setSources: (
      state,
      action: PayloadAction<{ conversionId: string; sources: SearchSource[] }>
    ) => {
      const chatState = conversationIdCheck(state, action.payload.conversionId);
      if (!isEmpty(chatState.messages)) {
        chatState.messages.at(-1)!.sources = action.payload.sources;
      }
    },
    setCallingTools: (
      state,
      action: PayloadAction<{ conversionId: string; isCallingTools: boolean }>
    ) => {
      const chatState = conversationIdCheck(state, action.payload.conversionId);
      chatState.isCallingTools = action.payload.isCallingTools;
    },
    prependContentToLastMessage: (
      state,
      action: PayloadAction<{ conversionId: string; content: string }>
    ) => {
      const chatState = conversationIdCheck(state, action.payload.conversionId);
      const lastMessage = lastMessageCheck(chatState.messages);
      if (lastMessage) {
        lastMessage.content = action.payload + lastMessage.content;
      }
    },
    appendContentToLastMessage: (
      state,
      action: PayloadAction<{ conversionId: string; content: string }>
    ) => {
      const chatState = conversationIdCheck(state, action.payload.conversionId);
      const lastMessage = lastMessageCheck(chatState.messages);
      if (lastMessage) {
        lastMessage.content += action.payload.content;
      }
    },
    prependSourceToLastReasoningMessage: (
      state,
      action: PayloadAction<{ conversionId: string; content: string }>
    ) => {
      const chatState = conversationIdCheck(state, action.payload.conversionId);
      const lastMessage = lastMessageCheck(chatState.messages);
      if (lastMessage && lastMessage.messageMetadata.thinkMode) {
        lastMessage.reasoning = action.payload.content + lastMessage.reasoning;
      }
    },
    appendReasoningToLastMessage: (
      state,
      action: PayloadAction<{ conversionId: string; content: string }>
    ) => {
      const chatState = conversationIdCheck(state, action.payload.conversionId);
      const lastMessage = lastMessageCheck(chatState.messages);
      if (lastMessage) {
        lastMessage.reasoning += action.payload.content;
      }
    },
    appendToolCallToLastMessage: (
      state,
      action: PayloadAction<{ conversionId: string; toolCall: ToolCallMessage }>
    ) => {
      const chatState = conversationIdCheck(state, action.payload.conversionId);
      const lastMessage = lastMessageCheck(chatState.messages);
      if (lastMessage) {
        lastMessage.toolCalls?.push(action.payload.toolCall);
      }
    },
    updateMessageStatus: (
      state,
      action: PayloadAction<{ conversionId: string; status: MessageStatus }>
    ) => {
      const chatState = conversationIdCheck(state, action.payload.conversionId);
      const lastMessage = lastMessageCheck(chatState.messages);
      if (lastMessage) {
        lastMessage.status = action.payload.status;
      }
    },
    clearCurrentChat: (
      state,
      action: PayloadAction<{ conversionId: string }>
    ) => {
      const chatState = conversationIdCheck(state, action.payload.conversionId);
      chatState.messages = [];
      chatState.isLoading = false;
      chatState.isStreaming = false;
      chatState.isReasoning = false;
      chatState.isCallingTools = false;
    },
  },
});

export const {
  setMessages,
  addMessage,
  addMessageAtIndex,
  removeMessageById,
  clearMessages,
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
  clearLastMessage,
  clearCurrentChat,
} = chatSlice.actions;

export default chatSlice.reducer;
