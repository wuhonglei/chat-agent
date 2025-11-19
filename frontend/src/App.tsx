import { App as AntdApp } from "antd";
import React, { useEffect } from "react";
import { Route, BrowserRouter, Routes } from "react-router-dom";
import MainLayout from "./components/Layout/MainLayout";
import { routes } from "./routes";
import { useAppDispatch } from "./store/hooks";
import { getMCPConfig } from "./store/slices/mcpSlice";
import { setMessageInstance } from "./utils/message";
import { loadConversations } from "./store/slices/conversationSlice";

const App: React.FC = () => {
  const dispatch = useAppDispatch();
  const { message } = AntdApp.useApp();

  useEffect(() => {
    // 初始化 message 实例
    setMessageInstance(message);
  }, [message]);

  useEffect(() => {
    // 在应用初始化时检查 Google Favicons API 可用性
    dispatch(getMCPConfig());
    dispatch(loadConversations());
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
