import { TimeIcon, renderIcon } from "../icons";
import type { ToolRendererRegistry } from "../types";

export const timeRenderers: ToolRendererRegistry[string] = {
  get_current_time: {
    icon: renderIcon(TimeIcon),
  },
};
