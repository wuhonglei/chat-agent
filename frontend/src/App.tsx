import { App as AntdApp } from "antd";
import React, { useEffect } from "react";
import { Route, BrowserRouter, Routes } from "react-router-dom";
import MainLayout from "./components/Layout/MainLayout";
import { routes } from "./routes";
import { useAppDispatch } from "./store/hooks";
import { getMCPConfig } from "./store/slices/mcpSlice";
import { setMessageInstance } from "./utils/message";
import { loadConversations } from "./store/slices/conversationSlice";
import { getUserDetail } from "./store/slices/userSlice";

const App: React.FC = () => {
  const dispatch = useAppDispatch();
  const { message } = AntdApp.useApp();

  useEffect(() => {
    // 初始化 message 实例
    setMessageInstance(message);
  }, [message]);

  useEffect(() => {
    const init = async () => {
      try {
        await dispatch(getUserDetail()).unwrap();
        dispatch(getMCPConfig());
        dispatch(loadConversations());
      } catch (error) {
        console.error("初始化失败", error);
      }
    };
    init();
  }, [dispatch]);

  return (
    <BrowserRouter
      future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
    >
      <MainLayout>
        <Routes>
          {routes.map((route, index) => (
            <Route key={index} path={route.path} element={route.element} />
          ))}
        </Routes>
      </MainLayout>
    </BrowserRouter>
  );
};

export default React.memo(App);
