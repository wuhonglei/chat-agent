import { ExcelBlock, ImageBlock, MarkdownBlock, PdfBlock, TextFileBlock } from "@/interfaces/contentBlock";

import { apiClient } from "./base";

export const fileAPI = {
  uploadAvatar: async (file: File): Promise<string> => {
    const formData = new FormData();
    formData.append("file", file);
    return await apiClient.post("/avatars/upload", formData, {
      headers: {
        "Content-Type": "multipart/form-data",
      },
    });
  },

  uploadChatAttachment: async (
    file: File,
    conversationId: string,
  ): Promise<ImageBlock | PdfBlock | ExcelBlock | MarkdownBlock | TextFileBlock> => {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("conversation_id", conversationId);
    return await apiClient.post("/file/upload", formData, {
      headers: {
        "Content-Type": "multipart/form-data",
      },
      timeout: 180000, // 3 minutes
    });
  },
};
