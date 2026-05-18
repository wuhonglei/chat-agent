import { useContext } from "react";
import { BlockPreviewContext, type BlockPreviewContextValue } from "./blockPreviewContext";

export function useBlockPreview(): BlockPreviewContextValue | null {
  return useContext(BlockPreviewContext);
}
