import { getSortedIconUrl } from "@/utils";
import { useMemo } from "react";

export function useWebIconUrls(sources: { url?: string; favicon?: string }[] | undefined, options: { max: number }) {
  const { max } = options;
  const sourcesString = JSON.stringify(sources || []);
  return useMemo(() => {
    const newUrls = JSON.parse(sourcesString);
    return newUrls
      .filter(Boolean)
      .slice(0, max)
      .map((source: { url?: string; favicon?: string }) => getSortedIconUrl(source.url, source.favicon));
  }, [sourcesString, max]);
}
