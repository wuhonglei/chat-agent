import { capitalize, words } from "lodash-es";

export function formatServerName(serverName?: string): string {
  if (!serverName) {
    return "";
  }
  return words(serverName).map(capitalize).join(" ");
}
