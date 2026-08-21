import { renderSkillLoadToolResult } from "../components/SkillLoadToolResult";
import type { ToolRendererRegistry } from "../types";

export const skillManagerRenderers: ToolRendererRegistry[string] = {
  load_skill: {
    renderResult: renderSkillLoadToolResult,
  },
};
