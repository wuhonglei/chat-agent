import { Layout } from "antd";
import React, { useEffect } from "react";
import { Route, BrowserRouter, Routes } from "react-router-dom";
import MainLayout from "./components/Layout/MainLayout";
import { routes } from "./routes";
import { useAppDispatch } from "./store/hooks";
import {
  checkGoogleFavIconsAvailability,
  getMCPConfig,
} from "./store/slices/globalSlice";

const { Content } = Layout;

const App: React.FC = () => {
  const dispatch = useAppDispatch();

  useEffect(() => {
    // 在应用初始化时检查 Google Favicons API 可用性
    dispatch(checkGoogleFavIconsAvailability());
    dispatch(getMCPConfig());
  }, [dispatch]);

  return (
    <BrowserRouter
      future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
    >
      <MainLayout>
        <Content className="h-full bg-gray-50">
          <Routes>
            {routes.map((route, index) => (
              <Route key={index} path={route.path} element={route.element} />
            ))}
          </Routes>
        </Content>
      </MainLayout>
    </BrowserRouter>
  );
};

export default React.memo(App);
