import { configureStore } from "@reduxjs/toolkit";
import chatReducer from "./slices/chatSlice";
import globalReducer from "./slices/globalSlice";
import conversationReducer from "./slices/conversationSlice";
import { dbMiddleware } from "./middleware/dbMiddleware";

export const store = configureStore({
  reducer: {
    chat: chatReducer,
    global: globalReducer,
    conversation: conversationReducer,
  },
  middleware: getDefaultMiddleware =>
    getDefaultMiddleware({
      serializableCheck: false,
    }).concat(dbMiddleware),
});

// Infer the `RootState` and `AppDispatch` types from the store itself
export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;
