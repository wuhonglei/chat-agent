import { renderMarkdownToolResult } from "../components/MarkdownToolResult";
import { getFilePathFromArgs, getLanguageFromFilePath } from "../utils/filePathLanguage";
import type { ToolRenderContext, ToolRendererRegistry } from "../types";

function fileResultLanguage(ctx: ToolRenderContext): string {
  const filePath = getFilePathFromArgs(ctx.toolUseBlock.argumentsJson);
  if (filePath) {
    const languageFromPath = getLanguageFromFilePath(filePath);
    if (languageFromPath) {
      return languageFromPath;
    }
  }
  return "markdown";
}

export const fileRenderers: ToolRendererRegistry[string] = {
  read_file: {
    renderResult: renderMarkdownToolResult,
    getResultLanguage: fileResultLanguage,
  },
  write_file: {
    getResultLanguage: fileResultLanguage,
  },
  edit_file: {
    getResultLanguage: fileResultLanguage,
  },
  search_files: {},
  present_files: {},
};
