import { useContainerWidth } from "@/hooks";
import { useMemo } from "react";

export function usePaddingHorizontal(childElement: HTMLElement | null) {
  const containerWidth = useContainerWidth(
    childElement?.parentElement?.parentElement?.parentElement
  );

  console.info("containerWidth", containerWidth);

  return useMemo(() => {
    if (containerWidth <= 768) {
      return 8;
    }
    return Math.max(8, Math.floor((containerWidth - 768) / 2));
  }, [containerWidth]);
}
