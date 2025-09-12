import { Layout } from "antd";
import React from "react";
import { Route, BrowserRouter as Router, Routes } from "react-router-dom";
import MainLayout from "./components/Layout/MainLayout";
import ChatPage from "./pages/ChatPage";
import DocumentsPage from "./pages/DocumentsPage";
import KnowledgeBasePage from "./pages/KnowledgeBasePage";

const { Content } = Layout;

const App: React.FC = () => {
  return (
    <Router>
      <MainLayout>
        <Content className="h-full bg-gray-50">
          <Routes>
            <Route path="/" element={<ChatPage />} />
            <Route path="/chat" element={<ChatPage />} />
            <Route path="/documents" element={<DocumentsPage />} />
            <Route path="/knowledge-base" element={<KnowledgeBasePage />} />
          </Routes>
        </Content>
      </MainLayout>
    </Router>
  );
};

export default App;
