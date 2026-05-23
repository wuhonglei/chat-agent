import type { PreviewableBlock } from "@/interfaces/contentBlock";
import { createContext } from "react";

export type BlockPreviewContextValue = {
  openPreview: (block: PreviewableBlock) => void;
};

export const BlockPreviewContext = createContext<BlockPreviewContextValue | null>(null);
