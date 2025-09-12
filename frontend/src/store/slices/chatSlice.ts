import { createAsyncThunk, createSlice, PayloadAction } from "@reduxjs/toolkit";
import { chatAPI } from "../../services/api";
import { ChatMessage, SearchSource } from "../../types";

interface ChatState {
  messages: ChatMessage[];
  sessionId: string | null;
  isLoading: boolean;
  isStreaming: boolean;
  error: string | null;
  sources: SearchSource[];
}

const initialState: ChatState = {
  messages: [],
  sessionId: null,
  isLoading: false,
  isStreaming: false,
  error: null,
  sources: [],
};

// Async thunks
export const sendMessage = createAsyncThunk(
  "chat/sendMessage",
  async ({
    message,
    sessionId,
    useKnowledgeBase = true,
  }: {
    message: string;
    sessionId?: string;
    useKnowledgeBase?: boolean;
  }) => {
    const response = await chatAPI.sendMessage({
      message,
      session_id: sessionId,
      use_knowledge_base: useKnowledgeBase,
    });
    return response.data;
  },
);

const chatSlice = createSlice({
  name: "chat",
  initialState,
  reducers: {
    addMessage: (state, action: PayloadAction<ChatMessage>) => {
      state.messages.push(action.payload);
    },
    clearMessages: (state) => {
      state.messages = [];
      state.sources = [];
    },
    setSessionId: (state, action: PayloadAction<string>) => {
      state.sessionId = action.payload;
    },
    setStreaming: (state, action: PayloadAction<boolean>) => {
      state.isStreaming = action.payload;
    },
    setSources: (state, action: PayloadAction<SearchSource[]>) => {
      state.sources = action.payload;
    },
    appendToLastMessage: (state, action: PayloadAction<string>) => {
      if (state.messages.length > 0) {
        const lastMessage = state.messages[state.messages.length - 1];
        if (lastMessage.role === "assistant") {
          lastMessage.content += action.payload;
        }
      }
    },
    clearError: (state) => {
      state.error = null;
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(sendMessage.pending, (state) => {
        state.isLoading = true;
        state.error = null;
      })
      .addCase(sendMessage.fulfilled, (state, action) => {
        state.isLoading = false;
        state.messages.push({
          role: "assistant",
          content: action.payload.message,
          timestamp: action.payload.timestamp,
        });
        state.sources = action.payload.sources || [];
        state.sessionId = action.payload.session_id;
      })
      .addCase(sendMessage.rejected, (state, action) => {
        state.isLoading = false;
        state.error = action.error.message || "Failed to send message";
      });
  },
});

export const {
  addMessage,
  clearMessages,
  setSessionId,
  setStreaming,
  setSources,
  appendToLastMessage,
  clearError,
} = chatSlice.actions;

export default chatSlice.reducer;
