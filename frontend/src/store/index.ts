import { configureStore } from "@reduxjs/toolkit";
import chatReducer from "./slices/chatSlice";
import mcpReducer from "./slices/mcpSlice";
import modelsReducer from "./slices/modelsSlice";
import conversationReducer from "./slices/conversationSlice";
import { dbMiddleware } from "./middleware/dbMiddleware";
import { updateLastMessageTimeMiddleware } from "./middleware/updateLastMessageTimeMiddleware";
import userReducer from "./slices/userSlice";

export const store = configureStore({
  reducer: {
    chat: chatReducer,
    mcp: mcpReducer,
    models: modelsReducer,
    conversation: conversationReducer,
    user: userReducer,
  },
  middleware: getDefaultMiddleware =>
    getDefaultMiddleware({
      serializableCheck: false,
    })
      .concat(updateLastMessageTimeMiddleware) // 先执行，更新 lastMessageUpdateAt
      .concat(dbMiddleware), // 再执行，保存到数据库
});

// Infer the `RootState` and `AppDispatch` types from the store itself
export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;
