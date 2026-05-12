import axios from "axios";
import { authHeader } from "@/constants/authHeader";
import { addRequestHeaders, apiClient } from "./base";

export interface WorkspaceTreeNode {
  title: string;
  path: string;
  fullPath?: string;
  nodeType?: "dir" | "file";
  hasChildren?: boolean;
  isLeaf?: boolean;
  key?: string;
  children?: WorkspaceTreeNode[];
}

export interface WorkspaceFileTreeResponse {
  workspaceId: string;
  path?: string;
  treeData: WorkspaceTreeNode[];
  updatedAt?: string;
}

export interface WorkspaceFileContentResponse {
  path: string;
  content: string;
  size?: number;
  updatedAt?: string;
}

export const workspaceAPI = {
  getWorkspaceFileTree: async (
    workspaceId: string,
    options?: { path?: string; depth?: number; includeIgnored?: boolean }
  ): Promise<WorkspaceFileTreeResponse> => {
    const { path = "", depth = 1, includeIgnored = false } = options || {};
    return await apiClient.get(`/workspaces/${workspaceId}/files`, {
      params: { path, depth, includeIgnored },
    });
  },
  getWorkspaceFileContent: async (workspaceId: string, path: string): Promise<WorkspaceFileContentResponse> => {
    return await apiClient.get(`/workspaces/${workspaceId}/file-content`, { params: { path } });
  },
  getWorkspacePreviewContent: async (workspaceId: string): Promise<string> => {
    const response = await axios.get<string>(workspaceAPI.getWorkspacePreviewContentUrl(workspaceId), {
      responseType: "text",
      headers: { Accept: "text/html" },
    });
    return response.data;
  },
  downloadWorkspaceZip: async (workspaceId: string): Promise<Blob> => {
    const response = await axios.get<Blob>(workspaceAPI.getWorkspaceDownloadUrl(workspaceId), {
      responseType: "blob",
      headers: addRequestHeaders({ Accept: "application/zip" }),
    });
    return response.data;
  },
  getWorkspacePreviewContentUrl: (workspaceId: string): string => {
    const userId = authHeader.getUserId();
    return `/api/workspaces/${encodeURIComponent(userId)}/${encodeURIComponent(workspaceId)}/preview-content`;
  },
  getWorkspaceDownloadUrl: (workspaceId: string): string => {
    return `/api/workspaces/${encodeURIComponent(workspaceId)}/download`;
  },
};
