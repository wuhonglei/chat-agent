import { renderMarkdownToolResult } from "../components/MarkdownToolResult";
import { LoadSkillIcon, renderIcon } from "../icons";
import type { ToolRendererRegistry } from "../types";

export const skillManagerRenderers: ToolRendererRegistry[string] = {
  load_skill: {
    icon: renderIcon(LoadSkillIcon),
    renderResult: renderMarkdownToolResult,
  },
};
