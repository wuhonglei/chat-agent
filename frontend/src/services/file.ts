import { ImageBlock, MarkdownBlock, PdfBlock } from "@/interfaces/contentBlock";

import { apiClient } from "./base";

export const fileAPI = {
  uploadAvatar: async (file: File): Promise<string> => {
    const formData = new FormData();
    formData.append("file", file);
    return await apiClient.post("/file/upload_avatar", formData, {
      headers: {
        "Content-Type": "multipart/form-data",
      },
    });
  },

  uploadChatAttachment: async (file: File): Promise<ImageBlock | PdfBlock | MarkdownBlock> => {
    const formData = new FormData();
    formData.append("file", file);
    return await apiClient.post("/file/upload", formData, {
      headers: {
        "Content-Type": "multipart/form-data",
      },
      timeout: 180000, // 3 minutes
    });
  },
};
