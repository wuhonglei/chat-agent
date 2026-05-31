import { DEFAULT_TOOL_RENDERER } from "./defaults";
import { DEFAULT_ICON } from "./icons";
import { codeRenderers } from "./servers/code";
import { context7Renderers } from "./servers/context7";
import { fileRenderers } from "./servers/file";
import { shellRenderers } from "./servers/shell";
import { skillManagerRenderers } from "./servers/skill_manager";
import { tavilyRenderers } from "./servers/tavily";
import { timeRenderers } from "./servers/time";
import { weatherRenderers } from "./servers/weather";
import type { ToolRenderer } from "./types";

export const DEFAULT_TOOL_RENDERER_ENTRY: ToolRenderer = {
  ...DEFAULT_TOOL_RENDERER,
  icon: DEFAULT_ICON,
};

export const SERVER_TOOL_RENDERERS: Record<string, Record<string, ToolRenderer>> = {
  tavily: tavilyRenderers,
  file: fileRenderers,
  code: codeRenderers,
  shell: shellRenderers,
  skill_manager: skillManagerRenderers,
  context7: context7Renderers,
  weather: weatherRenderers,
  time: timeRenderers,
};

/** @deprecated Use DEFAULT_TOOL_RENDERER_ENTRY + SERVER_TOOL_RENDERERS */
export const TOOL_RENDERER_REGISTRY = {
  _default: DEFAULT_TOOL_RENDERER_ENTRY,
  ...SERVER_TOOL_RENDERERS,
};
