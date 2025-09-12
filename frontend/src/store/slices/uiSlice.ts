import { createSlice, PayloadAction } from "@reduxjs/toolkit";
import { Notification } from "../../types";

interface UIState {
  theme: "light" | "dark";
  sidebarCollapsed: boolean;
  activeMenu: string;
  notifications: Notification[];
}

const initialState: UIState = {
  theme: "light",
  sidebarCollapsed: false,
  activeMenu: "chat",
  notifications: [],
};

const uiSlice = createSlice({
  name: "ui",
  initialState,
  reducers: {
    toggleTheme: (state) => {
      state.theme = state.theme === "light" ? "dark" : "light";
    },
    toggleSidebar: (state) => {
      state.sidebarCollapsed = !state.sidebarCollapsed;
    },
    setActiveMenu: (state, action: PayloadAction<string>) => {
      state.activeMenu = action.payload;
    },
    addNotification: (
      state,
      action: PayloadAction<Omit<Notification, "id">>,
    ) => {
      state.notifications.push({
        id: Date.now(),
        ...action.payload,
      });
    },
    removeNotification: (state, action: PayloadAction<string | number>) => {
      state.notifications = state.notifications.filter(
        (n) => n.id !== action.payload,
      );
    },
  },
});

export const {
  toggleTheme,
  toggleSidebar,
  setActiveMenu,
  addNotification,
  removeNotification,
} = uiSlice.actions;

export default uiSlice.reducer;
