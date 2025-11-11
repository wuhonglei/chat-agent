import ChatPage from "@/pages/ChatPage";
import EmptyChatPage from "@/pages/EmptyChatPage";
import MarkdownPage from "@/pages/MarkdownPage";
import { RouteObject, Navigate } from "react-router-dom";

export const routes: RouteObject[] = [
  {
    path: "/",
    element: <Navigate to="/chat" replace />,
  },
  {
    path: "/chat",
    element: <EmptyChatPage />, // 空聊天页面
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
