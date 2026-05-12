import { useMemo } from "react";
import type { RenderableContentBlock } from "./viewModel.ts";

export const useLastTextBlockIndex = (renderableBlocks: RenderableContentBlock[]) =>
  useMemo(() => {
    for (let index = renderableBlocks.length - 1; index >= 0; index -= 1) {
      if (renderableBlocks[index].type === "text") {
        return index;
      }
    }
    return -1;
  }, [renderableBlocks]);
