import { createAsyncThunk, createSlice } from "@reduxjs/toolkit";
import { UserAPI } from "@/services";
import { UserInfo } from "@/interfaces";

export const getUserDetail = createAsyncThunk(
  "user/getUserDetail",
  async () => {
    const userDetail = await UserAPI.getUserDetail();
    return userDetail;
  }
);

const userSlice = createSlice({
  name: "user",
  initialState: {
    userDetail: null as UserInfo | null,
  },
  reducers: {},
  extraReducers: builder => {
    builder.addCase(getUserDetail.fulfilled, (state, action) => {
      state.userDetail = action.payload;
    });
  },
});

export default userSlice.reducer;
