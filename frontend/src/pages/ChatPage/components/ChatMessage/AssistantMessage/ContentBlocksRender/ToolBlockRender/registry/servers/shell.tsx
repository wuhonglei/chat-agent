import { renderShellCommandArguments } from "../components/ShellCommandArguments";
import { renderShellToolResult } from "../components/ShellToolResult";
import { ShellIcon, renderIcon } from "../icons";
import type { ToolRendererRegistry } from "../types";

export const shellRenderers: ToolRendererRegistry[string] = {
  shell: {
    icon: renderIcon(ShellIcon),
    renderArguments: renderShellCommandArguments,
    renderResult: ctx => renderShellToolResult(ctx) ?? null,
  },
};
