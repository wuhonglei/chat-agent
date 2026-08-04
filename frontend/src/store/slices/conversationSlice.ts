import { ConversationInfo, CreateConversationRequest, UpdateConversationRequest } from "@/interfaces";
import { conversationAPI } from "@/services";
import { createAsyncThunk, createSlice, PayloadAction } from "@reduxjs/toolkit";
import { uniqBy } from "lodash-es";

interface ConversationState {
  // 对话列表
  conversations: ConversationInfo[];
  conversationsLoaded: boolean;

  // 当前对话信息
  conversationInfo: ConversationInfo | null;
  nextCursor: string | null;
  hasMore: boolean;
  limit: number;
}

const initialState: ConversationState = {
  conversations: [],
  conversationsLoaded: false,
  conversationInfo: null,
  nextCursor: null,
  hasMore: true,
  limit: 50,
};

// ==================== Async Thunks ====================

/**
 * 注册正式会话
 */
export const registerConversation = createAsyncThunk(
  "conversation/registerConversation",
  async (params?: CreateConversationRequest) => {
    return await conversationAPI.registerConversation(params);
  }
);

export const activateConversation = createAsyncThunk(
  "conversation/activateConversation",
  async (conversationId: string) => {
    return await conversationAPI.activateConversation(conversationId);
  }
);

export const deleteConversation = createAsyncThunk(
  "conversation/deleteConversation",
  async (conversationId: string) => {
    return await conversationAPI.deleteConversation(conversationId);
  }
);

/**
 * 加载对话列表（游标分页）
 */
export const loadConversations = createAsyncThunk(
  "conversation/loadConversations",
  async (params?: { limit?: number; cursor?: string | null }) => {
    return await conversationAPI.getConversations(params);
  }
);

/**
 * 加载对话详情摘要（不包含 messages 列表）
 */
export const getConversationDetail = createAsyncThunk(
  "conversation/getConversationDetail",
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

const findConversationIndexInListHelper = (state: ConversationState, conversationId: string): number => {
  return state.conversations.findIndex(conv => conv.id === conversationId);
};

// 辅助函数：更新列表中的对话信息
const updateConversationInListHelper = (state: ConversationState, conversation: ConversationInfo): number => {
  const index = findConversationIndexInListHelper(state, conversation.id);
  if (index !== -1) {
    state.conversations[index] = conversation;
  }

  return index;
};

const removeConversationFromListHelper = (state: ConversationState, conversationId: string): number => {
  const index = findConversationIndexInListHelper(state, conversationId);
  if (index !== -1) {
    state.conversations.splice(index, 1);
  }

  return index;
};

/**
 * 添加对话到列表最前面
 */
const prependConversationToListHelper = (state: ConversationState, conversation: ConversationInfo): number => {
  state.conversations.unshift(conversation);
  return 0;
};

/**
 * 设置当前对话信息
 */
const setCurrentConversationHelper = (state: ConversationState, conversation: ConversationInfo | null): void => {
  state.conversationInfo = conversation;
};

const publishConversationHelper = (state: ConversationState, conversation: ConversationInfo): void => {
  removeConversationFromListHelper(state, conversation.id);
  prependConversationToListHelper(state, conversation);
  setCurrentConversationHelper(state, conversation);
};

const conversationSlice = createSlice({
  name: "conversation",
  initialState,
  reducers: {
    // 设置对话信息
    setConversationInfo: (state, action: PayloadAction<ConversationInfo | null>) => {
      setCurrentConversationHelper(state, action.payload);
    },

    setConversationInfoById: (state, action: PayloadAction<string>) => {
      const id = action.payload;
      const conversation = state.conversations.find(conv => conv.id === id);
      if (conversation) {
        setCurrentConversationHelper(state, conversation);
      } else if (state.conversationInfo?.id !== id) {
        // 懒加载列表尚未包含该会话：清空以免展示错误会话，由 useConversationInfo 拉取详情
        setCurrentConversationHelper(state, null);
      }
    },

    // 添加对话到列表最前面
    addConversationToList: (state, action: PayloadAction<ConversationInfo>) => {
      prependConversationToListHelper(state, action.payload);
    },

    updateConversationInList: (state, action: PayloadAction<ConversationInfo>) => {
      updateConversationInListHelper(state, action.payload);
    },

    updateConversationModifiedTime: (
      state,
      action: PayloadAction<{
        conversationId: string;
        lastMessageUpdatedAt: string;
      }>
    ) => {
      const { conversationId, lastMessageUpdatedAt } = action.payload;
      const index = findConversationIndexInListHelper(state, conversationId);
      if (index !== -1) {
        state.conversations[index].lastMessageUpdatedAt = lastMessageUpdatedAt;
      }
      if (state.conversationInfo?.id === conversationId) {
        state.conversationInfo.lastMessageUpdatedAt = lastMessageUpdatedAt;
      }
    },

    // 当该会话中有新的聊天消息时，更新列表中的对话信息
    refreshConversionInList: (state, action: PayloadAction<ConversationInfo>) => {
      const newConversation = action.payload;
      removeConversationFromListHelper(state, newConversation.id); // 先移除旧的会话
      prependConversationToListHelper(state, newConversation); // 再添加新的会话到最前面
      if (state.conversationInfo?.id === newConversation.id) {
        // 如果当前会话是该会话，则更新当前会话信息
        setCurrentConversationHelper(state, newConversation);
      }
    },

    // 从列表中移除对话
    removeConversationFromList: (state, action: PayloadAction<string>) => {
      removeConversationFromListHelper(state, action.payload);
    },

    // 清除当前会话
    clearCurrentConversion: state => {
      setCurrentConversationHelper(state, null);
    },
  },
  extraReducers: builder => {
    // registerConversation
    builder.addCase(registerConversation.fulfilled, (state, action) => {
      publishConversationHelper(state, action.payload);
    });

    // activateConversation
    builder.addCase(activateConversation.fulfilled, (state, action) => {
      publishConversationHelper(state, action.payload);
    });

    // loadConversations：无 cursor 时替换列表，有 cursor 时追加（滚动加载更多）
    builder.addCase(loadConversations.fulfilled, (state, action) => {
      const { conversations, nextCursor, hasMore, limit } = action.payload;
      const cursor = action.meta.arg?.cursor;
      if (!cursor) {
        state.conversations = conversations;
        state.conversationsLoaded = true;
      } else {
        // 追加并去重（新会话置顶可能导致分页与首屏重叠）
        state.conversations = uniqBy([...state.conversations, ...conversations], "id");
      }
      state.nextCursor = nextCursor;
      state.hasMore = hasMore;
      state.limit = limit;
    });

    // updateConversationInfo
    builder.addCase(updateConversationInfo.fulfilled, (state, action) => {
      const conversation = action.payload;
      // 更新列表中的对话信息（复用辅助函数）
      updateConversationInListHelper(state, conversation);
      // 更新当前对话信息
      if (state.conversationInfo?.id === conversation.id) {
        setCurrentConversationHelper(state, conversation);
      }
    });

    // deleteConversation
    builder.addCase(deleteConversation.fulfilled, (state, action) => {
      const id = action.payload;
      removeConversationFromListHelper(state, id);
      // conversationInfo 的置空，由 MainLayout 组件中 调用的 hooks useConversionInfo 处理
    });

    builder.addCase(getConversationDetail.fulfilled, (state, action) => {
      const conversation = action.payload;
      const index = updateConversationInListHelper(state, conversation);
      // 搜索跳转等场景：列表未加载到该会话时补到顶部，便于侧边栏高亮
      if (index === -1) {
        prependConversationToListHelper(state, conversation);
      }
      // 直接更新当前对话信息，因为这是获取当前会话详情的操作
      setCurrentConversationHelper(state, conversation);
    });
  },
});

export const {
  setConversationInfo,
  setConversationInfoById,
  addConversationToList,
  updateConversationInList,
  updateConversationModifiedTime,
  refreshConversionInList,
  removeConversationFromList,
  clearCurrentConversion,
} = conversationSlice.actions;

export default conversationSlice.reducer;
