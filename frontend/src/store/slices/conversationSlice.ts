import { createAsyncThunk, createSlice, PayloadAction } from "@reduxjs/toolkit";
import {
  ConversationInfo,
  CreateConversationRequest,
  UpdateConversationRequest,
} from "@/interfaces";
import { conversationAPI } from "@/services";

interface ConversationState {
  // 对话列表
  conversations: ConversationInfo[];
  conversationsLoading: boolean;

  // 当前对话信息
  conversationInfo: ConversationInfo | null;

  // 会话状态
  isNewConversion: boolean; // 是否为新会话

  // 当前对话加载状态
  loadingConversation: boolean;

  total: number;
  offset: number;
  limit: number;
}

const initialState: ConversationState = {
  conversations: [],
  conversationsLoading: false,

  conversationInfo: null,
  isNewConversion: false,
  loadingConversation: false,
  total: 0,
  offset: 0,
  limit: 50,
};

// ==================== Async Thunks ====================

/**
 * 注册正式会话
 */
export const registerConversation = createAsyncThunk(
  "conversation/registerConversation",
  async (params?: CreateConversationRequest) => {
    return await conversationAPI.createConversation(params);
  }
);

export const deleteConversation = createAsyncThunk(
  "conversation/deleteConversation",
  async (conversationId: string) => {
    return await conversationAPI.deleteConversation(conversationId);
  }
);

/**
 * 加载对话列表
 */
export const loadConversations = createAsyncThunk(
  "conversation/loadConversations",
  async (params?: { limit?: number; offset?: number }) => {
    return await conversationAPI.getConversations(params);
  }
);

/**
 * 加载对话详情（包括历史消息）
 */
export const loadConversation = createAsyncThunk(
  "conversation/loadConversation",
  async (conversationId: string) => {
    return await conversationAPI.getConversation(conversationId);
  }
);

/**
 * 更新对话信息
 */
export const updateConversationInfo = createAsyncThunk(
  "conversation/updateConversationInfo",
  async (data: UpdateConversationRequest) => {
    return await conversationAPI.updateConversation(data.id, data);
  }
);
// ==================== Slice ====================

// 辅助函数：更新列表中的对话信息
const updateConversationInListHelper = (
  state: ConversationState,
  conversation: ConversationInfo
) => {
  const index = state.conversations.findIndex(
    conv => conv.id === conversation.id
  );
  if (index !== -1) {
    state.conversations[index] = conversation;
  }
};

const removeConversationFromListHelper = (
  state: ConversationState,
  conversationId: string
) => {
  const index = state.conversations.findIndex(
    conv => conv.id === conversationId
  );
  if (index !== -1) {
    state.conversations.splice(index, 1);
  }
};

const conversationSlice = createSlice({
  name: "conversation",
  initialState,
  reducers: {
    // 设置对话信息
    setConversationInfo: (
      state,
      action: PayloadAction<ConversationInfo | null>
    ) => {
      state.conversationInfo = action.payload;
    },

    // 添加对话到列表
    addConversationToList: (state, action: PayloadAction<ConversationInfo>) => {
      state.conversations.unshift(action.payload);
    },

    updateConversationInList: (
      state,
      action: PayloadAction<ConversationInfo>
    ) => {
      updateConversationInListHelper(state, action.payload);
    },

    // 从列表中移除对话
    removeConversationFromList: (state, action: PayloadAction<string>) => {
      removeConversationFromListHelper(state, action.payload);
    },

    // 清除当前会话
    clearCurrentSession: state => {
      state.conversationInfo = null;
      state.isNewConversion = false;
    },
  },
  extraReducers: builder => {
    // registerConversation
    builder
      .addCase(registerConversation.pending, state => {
        state.loadingConversation = true;
      })
      .addCase(registerConversation.fulfilled, (state, action) => {
        state.loadingConversation = false;
        state.conversations.unshift(action.payload);
      })
      .addCase(registerConversation.rejected, state => {
        state.loadingConversation = false;
      });

    // loadConversation
    builder
      .addCase(loadConversations.pending, state => {
        state.conversationsLoading = true;
      })
      .addCase(loadConversations.fulfilled, (state, action) => {
        state.conversationsLoading = false;
        state.conversations = action.payload.conversations;
        state.total = action.payload.total;
        state.offset = action.payload.offset;
        state.limit = action.payload.limit;
      })
      .addCase(loadConversations.rejected, (state, action) => {
        state.loadingConversation = false;
      });

    // updateConversationInfo
    builder.addCase(updateConversationInfo.fulfilled, (state, action) => {
      // 更新当前对话信息
      state.conversationInfo = action.payload;
      // 更新列表中的对话信息（复用辅助函数）
      updateConversationInListHelper(state, action.payload);
    });

    // deleteConversation
    builder.addCase(deleteConversation.fulfilled, (state, action) => {
      removeConversationFromListHelper(state, action.payload);
    });
  },
});

export const {
  setConversationInfo,
  addConversationToList,
  updateConversationInList,
  removeConversationFromList,
  clearCurrentSession,
} = conversationSlice.actions;

export default conversationSlice.reducer;
