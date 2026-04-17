import { useDebounce, useSize } from "ahooks";
import { RefObject, useCallback, useEffect, useState } from "react";

const MIN_PAGE_WIDTH = 240;

function getPdfPaddingX(containerWidth: number): number {
  if (containerWidth >= 880) return 80;
  if (containerWidth >= 640) return 48;
  if (containerWidth >= 480) return 32;
  return 16;
}

export const usePdfPageWidth = (contentRef: RefObject<HTMLDivElement | null>) => {
  const contentSize = useSize(contentRef);
  const widthDebounced = useDebounce(contentSize?.width, {
    wait: 100,
  });

  if (!widthDebounced) {
    return { pageWidth: 360, paddingX: 16 };
  }

  const paddingX = getPdfPaddingX(widthDebounced);
  const pageWidth = Math.max(widthDebounced - paddingX * 2, MIN_PAGE_WIDTH);

  return { pageWidth, paddingX };
};

const PDF_LOAD_ERROR_MESSAGE = "PDF 加载失败，请重试";

export const usePdfPreviewState = (pdfUrl: string) => {
  const [numPages, setNumPages] = useState(0);
  const [hasRenderedFirstPage, setHasRenderedFirstPage] = useState(false);
  const [loadErrorMessage, setLoadErrorMessage] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);

  const resetPreviewState = useCallback(() => {
    setNumPages(0);
    setHasRenderedFirstPage(false);
  }, []);

  const handleDocumentLoadSuccess = useCallback(({ numPages: loadedPages }: { numPages: number }) => {
    setNumPages(loadedPages);
    setLoadErrorMessage(null);
    setHasRenderedFirstPage(false);
  }, []);

  const handlePdfLoadError = useCallback(
    (error: Error) => {
      resetPreviewState();
      setLoadErrorMessage(error.message || PDF_LOAD_ERROR_MESSAGE);
    },
    [resetPreviewState]
  );

  const handleRetryPreview = useCallback(() => {
    resetPreviewState();
    setLoadErrorMessage(null);
    setReloadToken(previous => previous + 1);
  }, [resetPreviewState]);

  const markFirstPageAsRendered = useCallback(() => {
    setHasRenderedFirstPage(true);
  }, []);

  useEffect(() => {
    resetPreviewState();
    setLoadErrorMessage(null);
    setReloadToken(0);
  }, [pdfUrl, resetPreviewState]);

  return {
    numPages,
    loadErrorMessage,
    reloadToken,
    isPreviewReady: numPages > 0 && hasRenderedFirstPage,
    handleDocumentLoadSuccess,
    handlePdfLoadError,
    handleRetryPreview,
    markFirstPageAsRendered,
  };
};
