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
  conversationsLoaded: boolean;

  // 当前对话信息
  conversationInfo: ConversationInfo | null;

  total: number;
  offset: number;
  limit: number;
}

const initialState: ConversationState = {
  conversations: [],
  conversationsLoaded: false,
  conversationInfo: null,
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

    setConversationInfoById: (state, action: PayloadAction<string>) => {
      const id = action.payload;
      const conversation = state.conversations.find(conv => conv.id === id);
      if (conversation) {
        state.conversationInfo = conversation;
      } else {
        state.conversationInfo = null;
      }
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
    clearCurrentConversion: state => {
      state.conversationInfo = null;
    },
  },
  extraReducers: builder => {
    // registerConversation
    builder.addCase(registerConversation.fulfilled, (state, action) => {
      state.conversationInfo = action.payload;
      state.conversations.unshift(action.payload);
    });

    // loadConversations
    builder.addCase(loadConversations.fulfilled, (state, action) => {
      state.conversations = action.payload.conversations;
      state.total = action.payload.total;
      state.offset = action.payload.offset;
      state.limit = action.payload.limit;
      state.conversationsLoaded = true;
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
      const id = action.payload;
      removeConversationFromListHelper(state, id);
      if (id === state.conversationInfo?.id) {
        state.conversationInfo = null;
      }
    });
  },
});

export const {
  setConversationInfo,
  setConversationInfoById,
  addConversationToList,
  updateConversationInList,
  removeConversationFromList,
  clearCurrentConversion,
} = conversationSlice.actions;

export default conversationSlice.reducer;
