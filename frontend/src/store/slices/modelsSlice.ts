import { ChatModelItem } from "@/interfaces";
import { chatAPI } from "@/services";
import { createAsyncThunk, createSlice } from "@reduxjs/toolkit";

interface ModelsState {
  models: ChatModelItem[];
  loaded: boolean;
}

/** 接口返回前占位，与表单默认 modelID「default」一致；fetch 成功后会覆盖 */
const defaultModelsPlaceholder: ChatModelItem[] = [
  {
    modelId: "default",
    title: "默认模型",
    description: "默认模型，支持文本和图片输入",
    imageSupport: true,
  },
];

const initialState: ModelsState = {
  models: defaultModelsPlaceholder,
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
    });
  },
});

export default modelsSlice.reducer;
