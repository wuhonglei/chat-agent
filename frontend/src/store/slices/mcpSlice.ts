import { createAsyncThunk, createSlice } from "@reduxjs/toolkit";
import { healthAPI } from "@/services";
import { MCPConfigItem } from "@/interfaces";

// 获取 MCP 配置
export const getMCPConfig = createAsyncThunk("mcp/getMCPConfig", async () => {
  const mcpConfig = await healthAPI.getMCPConfig();
  return mcpConfig;
});

const mcpSlice = createSlice({
  name: "mcp",
  initialState: {
    mcpConfig: [] as MCPConfigItem[],
    mcpConfigLoaded: false,
  },
  reducers: {},
  extraReducers: builder => {
    builder.addCase(getMCPConfig.fulfilled, (state, action) => {
      state.mcpConfig = action.payload;
      state.mcpConfigLoaded = true;
    });
  },
});

export default mcpSlice.reducer;
