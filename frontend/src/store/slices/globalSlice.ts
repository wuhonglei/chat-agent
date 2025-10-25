import { createAsyncThunk, createSlice, PayloadAction } from "@reduxjs/toolkit";
import { checkGoogleFavIconsAvailable, healthAPI } from "@/services";
import { MCPConfigItem } from "@/interfaces";

// 检测 Google Fav icons API 是否可用
export const checkGoogleFavIconsAvailability = createAsyncThunk(
  "global/checkGoogleFavIcons",
  async (_, { dispatch }) => {
    const isAvailable = await checkGoogleFavIconsAvailable();
    dispatch(setGoogleFavIconsAvailable(isAvailable));
    return isAvailable;
  }
);

// 获取 MCP 配置
export const getMCPConfig = createAsyncThunk(
  "global/getMCPConfig",
  async (_, { dispatch }) => {
    const mcpConfig = await healthAPI.getMCPConfig();
    dispatch(setMCPConfig(mcpConfig));
  }
);
const globalSlice = createSlice({
  name: "global",
  initialState: {
    googleFavIconsAvailable: false,
    mcpConfig: [] as MCPConfigItem[],
    mcpConfigLoaded: false,
  },
  reducers: {
    setGoogleFavIconsAvailable: (state, action: PayloadAction<boolean>) => {
      state.googleFavIconsAvailable = action.payload;
    },
    setMCPConfig: (state, action: PayloadAction<MCPConfigItem[]>) => {
      state.mcpConfig = action.payload;
      state.mcpConfigLoaded = true;
    },
  },
});

export const { setGoogleFavIconsAvailable, setMCPConfig } = globalSlice.actions;

export default globalSlice.reducer;
