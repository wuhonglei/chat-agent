import { DEFAULT_THRESHOLD } from "@/constants";
import { useSize } from "ahooks";
import { useMemo } from "react";

export function useIsSmallScreen() {
  const { width } = useSize(document.body) || {};
  return useMemo(() => (width ? width <= DEFAULT_THRESHOLD : false), [width]);
}
