import { FILE_EXTENSION_LANGUAGE_MAP } from "@/constants";
import type { ToolResultBlock, ToolUseBlock } from "@/interfaces/contentBlock";
import { useMemo } from "react";

import { getResultLanguage } from "../utils";

type UseToolResultLanguageParams = {
  currentToolName?: string;
  toolResultBlock?: ToolResultBlock;
  toolUseBlock?: ToolUseBlock;
};

function getLanguageFromToolPath(path: string): string | undefined {
  const ext = path.split(".").pop()?.toLowerCase();
  if (!ext) {
    return undefined;
  }
  return FILE_EXTENSION_LANGUAGE_MAP[ext];
}

export function useToolResultLanguage({
  currentToolName,
  toolResultBlock,
  toolUseBlock,
}: UseToolResultLanguageParams): string {
  return useMemo(() => {
    if (currentToolName === "read_project_file") {
      const path = toolUseBlock?.argumentsJson?.path;
      if (typeof path === "string") {
        const languageFromPath = getLanguageFromToolPath(path);
        if (languageFromPath) {
          return languageFromPath;
        }
      }
    }
    return getResultLanguage(toolResultBlock?.content || "");
  }, [currentToolName, toolResultBlock?.content, toolUseBlock?.argumentsJson]);
}
