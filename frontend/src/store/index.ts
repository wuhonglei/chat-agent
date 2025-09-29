import { configureStore } from "@reduxjs/toolkit";
import chatReducer from "./slices/chatSlice";
import globalReducer from "./slices/globalSlice";

export const store = configureStore({
  reducer: {
    chat: chatReducer,
    global: globalReducer,
  },
});

// Infer the `RootState` and `AppDispatch` types from the store itself
export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;
