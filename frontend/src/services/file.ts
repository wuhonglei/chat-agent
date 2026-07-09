import {
  DocxBlock,
  ExcelBlock,
  ImageBlock,
  MarkdownBlock,
  PdfBlock,
  PptxBlock,
  TextFileBlock,
} from "@/interfaces/contentBlock";

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
  ): Promise<ImageBlock | PdfBlock | ExcelBlock | DocxBlock | PptxBlock | MarkdownBlock | TextFileBlock> => {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("conversation_id", conversationId);
    return await apiClient.post("/file/upload", formData, {
      headers: {
        "Content-Type": "multipart/form-data",
      },
      timeout: 300000, // 5 minutes（MinerU 轮询可能较久）
    });
  },
};
