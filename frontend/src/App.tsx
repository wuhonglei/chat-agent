import { Layout } from "antd";
import React from "react";
import { Route, BrowserRouter, Routes } from "react-router-dom";
import MainLayout from "./components/Layout/MainLayout";
import { routes } from "./routes";

const { Content } = Layout;

const App: React.FC = () => {
  return (
    <BrowserRouter>
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

export default App;
