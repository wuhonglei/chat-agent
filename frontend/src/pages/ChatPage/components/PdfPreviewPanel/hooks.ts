import { useSize } from "ahooks";
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

  return useMemo(() => {
    if (!contentSize?.width) return 360;
    return Math.max(contentSize.width - 24, 240);
  }, [contentSize?.width]);
};
