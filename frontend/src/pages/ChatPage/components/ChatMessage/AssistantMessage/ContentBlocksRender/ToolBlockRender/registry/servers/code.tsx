import { renderExecuteCodeArguments } from "../components/ExecuteCodeArguments";
import { CodeIcon, renderIcon } from "../icons";
import type { ToolRendererRegistry } from "../types";

export const codeRenderers: ToolRendererRegistry[string] = {
  execute_code: {
    icon: renderIcon(CodeIcon),
    renderArguments: renderExecuteCodeArguments,
  },
  list_runtimes: {
    icon: renderIcon(CodeIcon),
  },
};
