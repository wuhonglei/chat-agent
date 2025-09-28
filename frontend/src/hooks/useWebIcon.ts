import { getWebIconUrl } from "@/utils";
import { useMemo } from "react";

export function useWebIconUrls(
  sources: { url?: string; favicon?: string }[] | undefined,
  max: number
) {
  const sourcesString = JSON.stringify(sources || []);
  return useMemo(() => {
    const newUrls = JSON.parse(sourcesString);
    return newUrls
      .filter(Boolean)
      .slice(0, max)
      .map((source: { url?: string; favicon?: string }) => {
        return source.favicon || getWebIconUrl(source.url);
      });
  }, [sourcesString, max]);
}
