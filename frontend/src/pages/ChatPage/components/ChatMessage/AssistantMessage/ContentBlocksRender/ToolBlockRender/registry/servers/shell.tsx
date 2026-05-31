import { renderShellCommandArguments } from "../components/ShellCommandArguments";
import { renderShellToolResult } from "../components/ShellToolResult";
import type { ToolRendererRegistry } from "../types";

export const shellRenderers: ToolRendererRegistry[string] = {
  shell: {
    renderArguments: renderShellCommandArguments,
    renderResult: ctx => renderShellToolResult(ctx) ?? null,
  },
};
