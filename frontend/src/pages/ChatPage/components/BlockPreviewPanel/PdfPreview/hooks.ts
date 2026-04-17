import { useDebounce, useSize } from "ahooks";
import { RefObject, useCallback, useEffect, useState } from "react";

export const usePdfPageWidth = (contentRef: RefObject<HTMLDivElement | null>) => {
  const contentSize = useSize(contentRef);
  const widthDebounced = useDebounce(contentSize?.width, {
    wait: 100,
  });

  if (!widthDebounced) return 360;
  return Math.max(widthDebounced - 24, 240);
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
