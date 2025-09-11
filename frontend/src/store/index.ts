import { configureStore } from '@reduxjs/toolkit'
import chatReducer from './slices/chatSlice'
import documentReducer from './slices/documentSlice'
import uiReducer from './slices/uiSlice'

export const store = configureStore({
  reducer: {
    chat: chatReducer,
    document: documentReducer,
    ui: uiReducer,
  },
})

// Infer the `RootState` and `AppDispatch` types from the store itself
export type RootState = ReturnType<typeof store.getState>
export type AppDispatch = typeof store.dispatch