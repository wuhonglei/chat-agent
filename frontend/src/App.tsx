import React from "react";
import { BrowserRouter as Router, Routes, Route } from "react-router-dom";
import { Layout } from "antd";
import MainLayout from "./components/Layout/MainLayout";
import ChatPage from "./pages/ChatPage";
import DocumentsPage from "./pages/DocumentsPage";
import KnowledgeBasePage from "./pages/KnowledgeBasePage";

const { Content } = Layout;

const App: React.FC = () => {
  return (
    <Router>
      <MainLayout>
        <Content className="min-h-screen bg-gray-50">
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
