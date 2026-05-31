import { renderFileReadResult } from "../components/FileReadResult";
import { renderWriteFileArguments } from "../components/FileWriteArguments";
import { renderWriteFileResult } from "../components/FileWriteResult";
import type { ToolRendererRegistry } from "../types";

export const fileRenderers: ToolRendererRegistry[string] = {
  read_file: {
    renderResult: ctx => renderFileReadResult(ctx) ?? null,
  },
  write_file: {
    renderArguments: ctx => renderWriteFileArguments(ctx) ?? null,
    renderResult: ctx => renderWriteFileResult(ctx) ?? null,
  },
  edit_file: {},
  search_files: {},
  present_files: {},
};
