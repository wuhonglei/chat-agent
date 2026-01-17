import ChatPage from "@/pages/ChatPage";
import LoginPage from "@/pages/LoginPage";
import LoginCallback from "@/pages/LoginPage/components/WeChatLogin/LoginCallback";
import MarkdownPage from "@/pages/MarkdownPage";
import WelcomePage from "@/pages/WelcomePage";
import { Navigate, RouteObject } from "react-router-dom";

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
  {
    path: "/login",
    element: <LoginPage />,
  },
  {
    path: "/login/wechat/callback",
    element: <LoginCallback />,
  },
];
