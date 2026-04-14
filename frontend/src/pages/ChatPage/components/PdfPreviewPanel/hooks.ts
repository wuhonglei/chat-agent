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
  const widthDebounced = useDebounce(contentSize?.width, {
    wait: 100,
  });

  return useMemo(() => {
    if (!widthDebounced) return 360;
    return Math.max(widthDebounced - 24, 240);
  }, [widthDebounced]);
};
