import { UserInfo } from "@/interfaces";
import { userAPI } from "@/services";
import { createAsyncThunk, createSlice } from "@reduxjs/toolkit";

export const getUserDetail = createAsyncThunk(
  "user/getUserDetail",
  async () => {
    const userDetail = await userAPI.getUserDetail();
    return userDetail;
  }
);

export const logout = createAsyncThunk("user/logout", async () => {
  await userAPI.logout();
});

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

    builder.addCase(logout.fulfilled, state => {
      state.userDetail = null;
    });
  },
});

export const { clearUserDetail, setUserInfo } = userSlice.actions;
export default userSlice.reducer;
