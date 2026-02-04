import React from "react";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import MainLayout from "./components/Layout/MainLayout";
import { useAppInit, useMessageInstance } from "./hooks/app";
import { routes } from "./routes";

const App: React.FC = () => {
  useAppInit();
  useMessageInstance();

  return (
    <BrowserRouter>
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
