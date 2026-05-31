import { renderEditFileArguments } from "../components/FileEditArguments";
import { renderReadFileArguments } from "../components/FileReadArguments";
import { renderFileReadResult } from "../components/FileReadResult";
import { renderWriteFileArguments } from "../components/FileWriteArguments";
import { renderWriteFileResult } from "../components/FileWriteResult";
import type { ToolRendererRegistry } from "../types";

export const fileRenderers: ToolRendererRegistry[string] = {
  read_file: {
    renderArguments: ctx => renderReadFileArguments(ctx) ?? null,
    renderResult: ctx => renderFileReadResult(ctx) ?? null,
  },
  write_file: {
    renderArguments: ctx => renderWriteFileArguments(ctx) ?? null,
    renderResult: ctx => renderWriteFileResult(ctx) ?? null,
  },
  edit_file: {
    renderArguments: ctx => renderEditFileArguments(ctx) ?? null,
    renderResult: ctx => renderWriteFileResult(ctx) ?? null,
  },
  search_files: {},
  present_files: {},
};
