import { createAsyncThunk, createSlice, PayloadAction } from "@reduxjs/toolkit";
import { checkGoogleFavIconsAvailable } from "@/services";

// 检测 Google Fav icons API 是否可用
export const checkGoogleFavIconsAvailability = createAsyncThunk(
  "global/checkGoogleFavIcons",
  async (_, { dispatch }) => {
    const isAvailable = await checkGoogleFavIconsAvailable();
    dispatch(setGoogleFavIconsAvailable(isAvailable));
    return isAvailable;
  }
);

const globalSlice = createSlice({
  name: "global",
  initialState: {
    googleFavIconsAvailable: false,
  },
  reducers: {
    setGoogleFavIconsAvailable: (state, action: PayloadAction<boolean>) => {
      state.googleFavIconsAvailable = action.payload;
    },
  },
});

export const { setGoogleFavIconsAvailable } = globalSlice.actions;

export default globalSlice.reducer;
