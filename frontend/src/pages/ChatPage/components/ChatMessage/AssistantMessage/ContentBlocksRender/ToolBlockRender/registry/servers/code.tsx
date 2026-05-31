import { renderExecuteCodeArguments } from "../components/ExecuteCodeArguments";
import type { ToolRendererRegistry } from "../types";

export const codeRenderers: ToolRendererRegistry[string] = {
  execute_code: {
    renderArguments: renderExecuteCodeArguments,
  },
  list_runtimes: {},
};
