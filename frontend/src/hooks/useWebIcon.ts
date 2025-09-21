import { getWebIconUrl } from "@/utils";
import { useMemo } from "react";

export function useWebIconUrls(
  sources: { url?: string }[] | undefined,
  max: number
) {
  const urls = (sources || []).map(source => source.url);
  const urlsString = JSON.stringify(urls);
  return useMemo(() => {
    const newUrls = JSON.parse(urlsString);
    return newUrls
      .filter(Boolean)
      .slice(0, max)
      .map((url: string) => {
        return getWebIconUrl(url);
      });
  }, [urlsString, max]);
}
