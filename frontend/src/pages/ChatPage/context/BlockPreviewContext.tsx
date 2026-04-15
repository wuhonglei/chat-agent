import type { PreviewableBlock } from "@/interfaces/contentBlock";
import React, { createContext, useContext } from "react";

export type BlockPreviewContextValue = {
  openPreview: (block: PreviewableBlock) => void;
};

const BlockPreviewContext = createContext<BlockPreviewContextValue | null>(null);

export function BlockPreviewProvider({
  children,
  value,
}: {
  children: React.ReactNode;
  value: BlockPreviewContextValue;
}) {
  return <BlockPreviewContext.Provider value={value}>{children}</BlockPreviewContext.Provider>;
}

export function useBlockPreview(): BlockPreviewContextValue | null {
  return useContext(BlockPreviewContext);
}
