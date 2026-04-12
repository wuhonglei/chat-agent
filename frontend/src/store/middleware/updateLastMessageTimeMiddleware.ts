import { Middleware } from "@reduxjs/toolkit";
import { isEmpty } from "lodash-es";
import { ChatConversationState } from "@/interfaces";
import { updateMessageModifiedTime } from "../slices/chatSlice";

/**
 * Redux Middleware 用于自动更新 lastMessageUpdateAt
 * 当 messages 数组发生变化时，自动将 lastMessageUpdateAt 设置为最后一条消息的 updatedAt 时间
 */

// 修改 messages 数组的 actions
const MESSAGES_MODIFYING_ACTIONS = ["chat/setMessages", "chat/addMessage", "chat/replaceMessageById"];

/**
 * 从 action payload 中提取 conversationId
 */
const getConversationId = (action: {
  type: string;
  payload?: { conversationId?: string; [key: string]: unknown };
}): string | null => {
  if (action.payload?.conversationId) {
    return action.payload.conversationId;
  }
  return null;
};

/**
 * 获取最后一条消息的 updatedAt 时间
 */
const getLastMessageUpdateAt = (chatState: ChatConversationState): string => {
  if (isEmpty(chatState.messages)) {
    return "";
  }
  const lastMessage = chatState.messages.at(-1);
  return lastMessage?.updatedAt || "";
};

export const updateLastMessageTimeMiddleware: Middleware = store => next => action => {
  // 先执行 action，更新 state
  const result = next(action);

  // 类型检查：确保 action 有 type 属性
  if (typeof action !== "object" || action === null || !("type" in action)) {
    return result;
  }

  const actionType = String(action.type);

  // 只处理修改 messages 数组的 actions
  if (MESSAGES_MODIFYING_ACTIONS.includes(actionType)) {
    const conversationId = getConversationId(
      action as {
        type: string;
        payload?: { conversationId?: string; [key: string]: unknown };
      }
    );

    if (conversationId) {
      // 此时 state 已经被 reducer 更新，可以获取最新值
      const state = store.getState();
      const chatState: ChatConversationState | undefined = state.chat[conversationId];

      if (chatState) {
        const lastMessageUpdateAt = getLastMessageUpdateAt(chatState);

        // 只有当 lastMessageUpdateAt 与当前值不同时才更新，避免不必要的更新
        if (chatState.lastMessageUpdateAt !== lastMessageUpdateAt) {
          // 使用 dispatch 来更新，保持状态更新的统一性
          store.dispatch(
            updateMessageModifiedTime({
              conversationId,
              data: lastMessageUpdateAt,
            })
          );
        }
      }
    }
  }

  return result;
};
