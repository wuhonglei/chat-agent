import { useEffect } from "react";

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
