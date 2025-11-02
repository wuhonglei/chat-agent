import {
  ChatMessage,
  ConversationInfo,
  SearchSource,
  ToolCallMessage,
} from "@/interfaces";
import { createSlice, PayloadAction } from "@reduxjs/toolkit";
import { isEmpty } from "lodash-es";

interface ChatState {
  messages: ChatMessage[];
  conversationInfo: ConversationInfo | null;
  isLoading: boolean;
  isStreaming: boolean;
  isReasoning: boolean;
  isCallingTools: boolean;
  error: string | null;
}

const initialState: ChatState = {
  messages: [],
  conversationInfo: null,
  isLoading: false,
  isStreaming: false,
  isReasoning: false,
  isCallingTools: false,
  error: null,
};

/**
 * 检查消息列表中最后一个消息是否为助手消息
 * @param messages
 * @returns
 */
function lastMessageCheck(messages: ChatMessage[]): ChatMessage | undefined {
  if (isEmpty(messages)) {
    return undefined;
  }

  return messages.at(-1)?.role === "assistant" ? messages.at(-1) : undefined;
}

const chatSlice = createSlice({
  name: "chat",
  initialState,
  reducers: {
    addMessage: (state, action: PayloadAction<ChatMessage>) => {
      state.messages.push(action.payload);
    },
    addMessageAtIndex: (
      state,
      action: PayloadAction<{ message: ChatMessage; index: number }>
    ) => {
      // 插入到指定位置
      state.messages.splice(action.payload.index, 0, action.payload.message);
      // 清除该位置之后的所有消息
      state.messages.length = action.payload.index + 1;
    },
    clearLastMessage: state => {
      const lastMessage = lastMessageCheck(state.messages);
      if (lastMessage) {
        state.messages.pop();
      }
    },
    clearMessages: state => {
      state.messages = [];
    },
    setConversationInfo: (state, action: PayloadAction<ConversationInfo>) => {
      state.conversationInfo = action.payload;
    },
    setStreaming: (state, action: PayloadAction<boolean>) => {
      state.isStreaming = action.payload;
    },
    setLoading: (state, action: PayloadAction<boolean>) => {
      state.isLoading = action.payload;
    },
    setReasoning: (state, action: PayloadAction<boolean>) => {
      state.isReasoning = action.payload;
    },
    setSources: (state, action: PayloadAction<SearchSource[]>) => {
      state.messages[state.messages.length - 1].sources = action.payload;
    },
    setCallingTools: (state, action: PayloadAction<boolean>) => {
      state.isCallingTools = action.payload;
    },
    prependContentToLastMessage: (state, action: PayloadAction<string>) => {
      const lastMessage = lastMessageCheck(state.messages);
      if (lastMessage) {
        lastMessage.content = action.payload + lastMessage.content;
      }
    },
    appendContentToLastMessage: (state, action: PayloadAction<string>) => {
      const lastMessage = lastMessageCheck(state.messages);
      if (lastMessage) {
        lastMessage.content += action.payload;
      }
    },
    prependSourceToLastReasoningMessage: (
      state,
      action: PayloadAction<string>
    ) => {
      const lastMessage = lastMessageCheck(state.messages);
      if (lastMessage && lastMessage.messageMetadata.thinkMode) {
        lastMessage.reasoning = action.payload + lastMessage.reasoning;
      }
    },
    appendReasoningToLastMessage: (state, action: PayloadAction<string>) => {
      const lastMessage = lastMessageCheck(state.messages);
      if (lastMessage) {
        lastMessage.reasoning += action.payload;
      }
    },
    appendToolCallToLastMessage: (
      state,
      action: PayloadAction<ToolCallMessage>
    ) => {
      const lastMessage = lastMessageCheck(state.messages);
      if (lastMessage) {
        if (!lastMessage.toolCalls) {
          lastMessage.toolCalls = [];
        }
        lastMessage.toolCalls.push(action.payload);
      }
    },
    clearError: state => {
      state.error = null;
    },
  },
});

export const {
  addMessage,
  addMessageAtIndex,
  clearMessages,
  setConversationInfo,
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
  clearError,
  clearLastMessage,
} = chatSlice.actions;

export default chatSlice.reducer;
