import { renderMarkdownToolResult } from "../components/MarkdownToolResult";
import {
  EditFileIcon,
  PresentFilesIcon,
  ReadFileIcon,
  SearchFilesIcon,
  WriteFileIcon,
  renderIcon,
} from "../icons";
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
    icon: renderIcon(ReadFileIcon),
    renderResult: renderMarkdownToolResult,
    getResultLanguage: fileResultLanguage,
  },
  write_file: {
    icon: renderIcon(WriteFileIcon),
    getResultLanguage: fileResultLanguage,
  },
  edit_file: {
    icon: renderIcon(EditFileIcon),
    getResultLanguage: fileResultLanguage,
  },
  search_files: {
    icon: renderIcon(SearchFilesIcon),
  },
  present_files: {
    icon: renderIcon(PresentFilesIcon),
  },
};
