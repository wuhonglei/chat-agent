import type { ToolRenderer } from "./types";

export function mergeToolRenderer(custom: ToolRenderer | undefined, fallback: ToolRenderer): ToolRenderer {
  if (!custom) {
    return fallback;
  }
  return {
    renderArguments: custom.renderArguments ?? fallback.renderArguments,
    renderResult: custom.renderResult ?? fallback.renderResult,
    getResultLanguage: custom.getResultLanguage ?? fallback.getResultLanguage,
  };
}
