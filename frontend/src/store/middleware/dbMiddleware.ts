import { Middleware } from "@reduxjs/toolkit";
import { db } from "@/indexDB";
import { ChatConversationState } from "@/interfaces";
import { getDefaultChatState } from "../slices/chatSlice";
import { pick } from "lodash-es";

/**
 * Redux Middleware 用于处理数据库持久化操作
 * 将副作用从 reducers 中分离出来，保持 reducers 的纯净性
 *
 * 执行顺序说明：
 * 1. Middleware 在 reducer 之前开始执行（可以拦截/修改 action）
 * 2. next(action) 会继续传递 action 给后续 middleware 和 reducer
 * 3. next(action) 之后的代码在 reducer 执行之后执行
 * 4. 因此这里可以安全地获取 reducer 更新后的最新 state
 */

/**
 * 从 action payload 中提取 conversationId
 * 不同的 action payload 结构可能不同，需要统一处理
 */
const getConversationId = (action: {
  type: string;
  payload?: { conversationId?: string; [key: string]: unknown };
}): string | null => {
  // 大部分 chat actions 的 payload 结构是 { conversationId, data }
  if (action.payload?.conversationId) {
    return action.payload.conversationId;
  }
  return null;
};

export const dbMiddleware: Middleware = store => next => action => {
  // next(action) 会执行后续的 middleware 链和 reducer，更新 state
  const result = next(action);

  // 类型检查：确保 action 有 type 属性
  if (typeof action !== "object" || action === null || !("type" in action)) {
    return result;
  }

  const actionType = String(action.type);

  // 监听所有 chatSlice 的 actions（action type 以 "chat/" 开头）
  // 但排除临时状态的 actions
  if (actionType.startsWith("chat/")) {
    const conversationId = getConversationId(
      action as {
        type: string;
        payload?: { conversationId?: string; [key: string]: unknown };
      }
    );

    if (conversationId) {
      // 此时 state 已经被 reducer 更新，可以获取最新值
      const state = store.getState();
      const chatState: ChatConversationState = state.chat[conversationId];

      if (chatState) {
        // 对于 clearChatState，需要从数据库删除
        if (actionType === "chat/clearChatState") {
          db.conversationMessages.delete(conversationId).catch(error => {
            console.error(
              "Failed to delete conversation from IndexedDB:",
              error
            );
          });
        } else {
          // 其他 actions：异步保存到数据库，不阻塞 reducer 执行
          db.conversationMessages
            .put({
              id: conversationId,
              data: {
                ...getDefaultChatState(),
                ...pick(chatState, [
                  "messages",
                  "messageLoaded",
                  "lastMessageUpdateAt",
                ]),
              },
            })
            .catch(error => {
              console.error("Failed to save messages to IndexedDB:", error);
              // 可以在这里添加错误处理逻辑，比如显示错误提示
            });
        }
      }
    }
  }

  return result;
};
