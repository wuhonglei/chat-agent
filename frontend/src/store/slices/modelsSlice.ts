import { ChatModelItem } from "@/interfaces";
import { chatAPI } from "@/services";
import { createAsyncThunk, createSlice } from "@reduxjs/toolkit";

interface ModelsState {
  models: ChatModelItem[];
  loaded: boolean;
}

/** 不再硬编码默认模型：首屏 loading 时模型列表为空，等 /models 返回后由 models[0] 作为默认 */
const initialState: ModelsState = {
  models: [],
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
