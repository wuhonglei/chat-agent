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

const initialState: ChatState = getDefaultChatState();

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
    setMessages: (state, action: PayloadAction<ChatMessage[]>) => {
      state.messages = action.payload;
    },
    addMessage: (state, action: PayloadAction<ChatMessage>) => {
      state.messages.push(action.payload);
    },
    addMessageAtIndex: (
      state,
      action: PayloadAction<{ index: number; message: ChatMessage }>
    ) => {
      // 插入到指定位置
      state.messages.splice(action.payload.index, 0, action.payload.message);
      // 清除该位置之后的所有消息
      state.messages.length = action.payload.index + 1;
    },
    removeMessageById: (state, action: PayloadAction<string>) => {
      const index = state.messages.findIndex(
        message => message.id === action.payload
      );
      if (index !== -1) {
        state.messages.splice(index, 1);
      }
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
      if (!isEmpty(state.messages)) {
        state.messages.at(-1)!.sources = action.payload;
      }
    },
    setCallingTools: (state, action: PayloadAction<boolean>) => {
      const lastMessage = lastMessageCheck(state.messages);
      if (lastMessage) {
        state.isCallingTools = action.payload;
      }
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
        lastMessage.toolCalls.push(action.payload);
      }
    },
    updateMessageStatus: (state, action: PayloadAction<MessageStatus>) => {
      const lastMessage = lastMessageCheck(state.messages);
      if (lastMessage) {
        lastMessage.status = action.payload;
      }
    },
    clearCurrentChat: state => {
      state.messages = [];
      state.isLoading = false;
      state.isStreaming = false;
      state.isReasoning = false;
      state.isCallingTools = false;
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
