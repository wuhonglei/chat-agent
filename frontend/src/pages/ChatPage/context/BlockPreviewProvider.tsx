import type { ReactNode } from "react";
import { BlockPreviewContext, type BlockPreviewContextValue } from "./blockPreviewContext";

export function BlockPreviewProvider({ children, value }: { children: ReactNode; value: BlockPreviewContextValue }) {
  return <BlockPreviewContext.Provider value={value}>{children}</BlockPreviewContext.Provider>;
}
