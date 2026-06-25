import { authHeader } from "@/constants/authHeader";
import axios from "axios";
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

const WORKSPACE_FILE_LOAD_ERROR = "文件加载失败";

/** 原始文件接口在出错时返回 ApiResponse JSON，按 responseType 解析出后端 msg。 */
function extractWorkspaceFileError(error: unknown): Error {
  if (axios.isAxiosError(error)) {
    const data = error.response?.data;
    let msg: string | undefined;
    if (typeof data === "string") {
      try {
        msg = (JSON.parse(data) as { msg?: string }).msg;
      } catch {
        // 非 JSON 响应体，忽略
      }
    } else if (data instanceof ArrayBuffer) {
      try {
        msg = (JSON.parse(new TextDecoder().decode(data)) as { msg?: string }).msg;
      } catch {
        // 非 JSON 响应体，忽略
      }
    }
    return new Error(msg || error.message || WORKSPACE_FILE_LOAD_ERROR);
  }
  return error instanceof Error ? error : new Error(WORKSPACE_FILE_LOAD_ERROR);
}

export const workspaceAPI = {
  getWorkspaceFileTree: async (
    workspaceId: string,
    options?: { path?: string; depth?: number; includeIgnored?: boolean }
  ): Promise<WorkspaceFileTreeResponse> => {
    const { path = "", depth = 1, includeIgnored = false } = options || {};
    return await apiClient.get(`/user_data/${workspaceId}/files`, {
      params: { path, depth, includeIgnored },
    });
  },
  getWorkspaceFileText: async (workspaceId: string, path: string): Promise<string> => {
    try {
      const response = await axios.get<string>(`/api/user_data/${workspaceId}/file`, {
        params: { path },
        responseType: "text",
        headers: addRequestHeaders({}),
      });
      return response.data;
    } catch (error) {
      throw extractWorkspaceFileError(error);
    }
  },
  getWorkspaceFileBuffer: async (workspaceId: string, path: string): Promise<ArrayBuffer> => {
    try {
      const response = await axios.get<ArrayBuffer>(`/api/user_data/${workspaceId}/file`, {
        params: { path },
        responseType: "arraybuffer",
        headers: addRequestHeaders({}),
      });
      return response.data;
    } catch (error) {
      throw extractWorkspaceFileError(error);
    }
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
    return `/api/user_data/${encodeURIComponent(userId)}/${encodeURIComponent(workspaceId)}/preview-content`;
  },
  getWorkspaceDownloadUrl: (workspaceId: string): string => {
    return `/api/user_data/${encodeURIComponent(workspaceId)}/download`;
  },
};
