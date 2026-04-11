import { capitalize, words } from "lodash-es";

export function formatToolName(name?: string): string {
  if (!name) {
    return "未知工具";
  }

  const formattedName = words(name).map(capitalize).join(" ");
  return formattedName || "未知工具";
}
