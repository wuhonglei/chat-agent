import React from "react";
import ChatPage from "@/pages/ChatPage";
import DocumentsPage from "@/pages/DocumentsPage";
import KnowledgeBasePage from "@/pages/KnowledgeBasePage";
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
    path: "/documents",
    element: <DocumentsPage />,
  },
  {
    path: "/knowledge-base",
    element: <KnowledgeBasePage />,
  },
  {
    path: "/markdown",
    element: <MarkdownPage />,
  },
];
