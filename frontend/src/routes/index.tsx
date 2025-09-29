import React from "react";
import ChatPage from "@/pages/ChatPage";
import MarkdownPage from "@/pages/MarkdownPage";

export interface RouteConfig {
  path: string;
  element: React.ReactElement;
}

export const routes: RouteConfig[] = [
  {
    path: "/",
    element: <ChatPage />,
  },
  {
    path: "/chat",
    element: <ChatPage />,
  },
  {
    path: "/markdown",
    element: <MarkdownPage />,
  },
];
