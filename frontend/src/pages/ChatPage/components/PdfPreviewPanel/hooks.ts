import { useDebounce, useSize } from "ahooks";
import { RefObject, useEffect, useMemo } from "react";

interface UsePdfPreviewAutoCloseOnSmallScreenParams {
  isSmallScreen: boolean;
  hasPreviewingPdf: boolean;
  onClose: () => void;
}

export const usePdfPreviewAutoCloseOnSmallScreen = ({
  isSmallScreen,
  hasPreviewingPdf,
  onClose,
}: UsePdfPreviewAutoCloseOnSmallScreenParams) => {
  useEffect(() => {
    if (!isSmallScreen || !hasPreviewingPdf) {
      return;
    }
    onClose();
  }, [hasPreviewingPdf, isSmallScreen, onClose]);
};

export const usePdfPageWidth = (contentRef: RefObject<HTMLDivElement | null>) => {
  const contentSize = useSize(contentRef);
  const contentSizeDebounced = useDebounce(contentSize, {
    wait: 100,
  });

  return useMemo(() => {
    if (!contentSizeDebounced?.width) return 360;
    return Math.max(contentSizeDebounced.width - 24, 240);
  }, [contentSizeDebounced?.width]);
};
