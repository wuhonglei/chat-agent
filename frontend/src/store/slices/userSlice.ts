import { createAsyncThunk, createSlice } from "@reduxjs/toolkit";
import { userAPI } from "@/services";
import { UserInfo } from "@/interfaces";

export const getUserDetail = createAsyncThunk(
  "user/getUserDetail",
  async () => {
    const userDetail = await userAPI.getUserDetail();
    return userDetail;
  }
);

const userSlice = createSlice({
  name: "user",
  initialState: {
    userDetail: null as UserInfo | null,
  },
  reducers: {
    clearUserDetail: state => {
      state.userDetail = null;
    },
    setUserInfo: (state, action) => {
      state.userDetail = action.payload;
    },
  },
  extraReducers: builder => {
    builder.addCase(getUserDetail.fulfilled, (state, action) => {
      state.userDetail = action.payload;
    });
  },
});

export const { clearUserDetail, setUserInfo } = userSlice.actions;
export default userSlice.reducer;
