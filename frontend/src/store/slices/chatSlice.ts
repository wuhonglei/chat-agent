import { chatAPI } from "@/services/api";
import { ChatInputFormValues, ChatMessage, SearchSource } from "@/types";
import { createAsyncThunk, createSlice, PayloadAction } from "@reduxjs/toolkit";
import { isEmpty } from "lodash-es";

interface ChatState {
  messages: ChatMessage[];
  sessionId: string | null;
  isLoading: boolean;
  isStreaming: boolean;
  isReasoning: boolean;
  error: string | null;
}

const initialState: ChatState = {
  messages: [],
  sessionId: null,
  isLoading: false,
  isStreaming: false,
  isReasoning: false,
  error: null,
};

// Async thunks
export const sendMessage = createAsyncThunk(
  "chat/sendMessage",
  async (data: ChatInputFormValues & { sessionId: string }) => {
    const response = await chatAPI.sendMessage(data);
    return response.data;
  }
);

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
      if (lastMessage && !lastMessage.content) {
        state.messages.pop();
      }
    },
    clearMessages: state => {
      state.messages = [];
    },
    setSessionId: (state, action: PayloadAction<string>) => {
      state.sessionId = action.payload;
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
    prependToLastMessage: (state, action: PayloadAction<string>) => {
      const lastMessage = lastMessageCheck(state.messages);
      if (lastMessage) {
        lastMessage.content = action.payload + lastMessage.content;
      }
    },
    appendToLastMessage: (state, action: PayloadAction<string>) => {
      const lastMessage = lastMessageCheck(state.messages);
      if (lastMessage) {
        lastMessage.content += action.payload;
      }
    },
    appendToLastMessageReasoning: (state, action: PayloadAction<string>) => {
      const lastMessage = lastMessageCheck(state.messages);
      if (lastMessage) {
        lastMessage.reasoning += action.payload;
      }
    },
    clearError: state => {
      state.error = null;
    },
  },
  extraReducers: builder => {
    builder
      .addCase(sendMessage.pending, state => {
        state.isLoading = true;
        state.error = null;
        console.info("sendMessage.pending");
      })
      .addCase(sendMessage.fulfilled, (state, action) => {
        state.isLoading = false;
        state.messages.push({
          reasoning: "",
          role: "assistant",
          content: action.payload.message,
          sources: action.payload.sources || [],
          timestamp: action.payload.timestamp,
        });
        state.sessionId = action.payload.session_id;
        console.info("sendMessage.fulfilled");
      })
      .addCase(sendMessage.rejected, (state, action) => {
        state.isLoading = false;
        state.error = action.error.message || "Failed to send message";
        console.info("sendMessage.rejected");
      });
  },
});

export const {
  addMessage,
  addMessageAtIndex,
  clearMessages,
  setSessionId,
  setStreaming,
  setLoading,
  setSources,
  prependToLastMessage,
  appendToLastMessage,
  appendToLastMessageReasoning,
  setReasoning,
  clearError,
  clearLastMessage,
} = chatSlice.actions;

export default chatSlice.reducer;
