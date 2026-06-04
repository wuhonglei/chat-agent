import { ChatModelItem } from "@/interfaces";
import { chatAPI } from "@/services";
import { createAsyncThunk, createSlice } from "@reduxjs/toolkit";

interface ModelsState {
  models: ChatModelItem[];
  loaded: boolean;
}

/** 缓存上一次的模型列表，避免刷新时模型名先空后跳的抖动；版本前缀便于后续结构变更 */
const MODELS_CACHE_KEY = "chat-models-cache-v1";

function loadCachedModels(): ChatModelItem[] {
  try {
    const raw = localStorage.getItem(MODELS_CACHE_KEY);
    if (!raw) {
      return [];
    }
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? (parsed as ChatModelItem[]) : [];
  } catch {
    // 隐私模式 / 解析失败时静默回退为空列表
    return [];
  }
}

function saveCachedModels(models: ChatModelItem[]): void {
  try {
    localStorage.setItem(MODELS_CACHE_KEY, JSON.stringify(models));
  } catch {
    // 隐私模式 / 配额超限时忽略写入失败
  }
}

/**
 * 不再硬编码默认模型：
 * - 首屏用 localStorage 缓存的历史模型列表 hydrate，使已选模型立即显示 name（无抖动）
 * - loaded 仍为 false，待 /models 返回后覆盖列表并由 models[0] 决定默认
 */
const initialState: ModelsState = {
  models: loadCachedModels(),
  loaded: false,
};

export const fetchModels = createAsyncThunk("models/fetchModels", async () => {
  return await chatAPI.getChatModels();
});

const modelsSlice = createSlice({
  name: "models",
  initialState,
  reducers: {},
  extraReducers: builder => {
    builder.addCase(fetchModels.fulfilled, (state, action) => {
      state.models = action.payload;
      state.loaded = true;
      saveCachedModels(action.payload);
    });
  },
});

export default modelsSlice.reducer;
