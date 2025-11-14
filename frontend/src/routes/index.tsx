import ChatPage from "@/pages/ChatPage";
import WelcomePage from "@/pages/WelcomePage";
import MarkdownPage from "@/pages/MarkdownPage";
import { RouteObject, Navigate } from "react-router-dom";

export const routes: RouteObject[] = [
  {
    path: "/",
    element: <Navigate to="/chat" replace />,
  },
  {
    path: "/chat",
    element: <WelcomePage />, // 空聊天页面
  },
  {
    path: "/chat/:conversationId",
    element: <ChatPage />,
  },
  {
    path: "/markdown",
    element: <MarkdownPage />,
  },
];
