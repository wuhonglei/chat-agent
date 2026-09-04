import { useRequest } from "ahooks";
import { useCallback, useState } from "react";

const PDF_LOAD_ERROR_MESSAGE = "PDF 加载失败，请重试";

export const usePdfPreviewState = (pdfUrl: string) => {
  const [numPages, setNumPages] = useState(0);
  const [hasRenderedFirstPage, setHasRenderedFirstPage] = useState(false);
  const [loadErrorMessage, setLoadErrorMessage] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);
  const [sourceUrl, setSourceUrl] = useState(pdfUrl);

  if (sourceUrl !== pdfUrl) {
    setSourceUrl(pdfUrl);
    setNumPages(0);
    setHasRenderedFirstPage(false);
    setLoadErrorMessage(null);
    setReloadToken(0);
  }

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

const MARKDOWN_LOAD_ERROR = "Markdown 加载失败";

async function fetchMarkdownAsText(url: string): Promise<string> {
  const res = await fetch(url, { credentials: "include" });
  if (!res.ok) {
    throw new Error(res.status === 404 ? "文件不存在" : `加载失败 (${res.status})`);
  }
  return res.text();
}

export function useMarkdownPreviewContent(markdownUrl: string | undefined, enabled: boolean) {
  const ready = Boolean(enabled && markdownUrl);

  const {
    data: text,
    loading,
    error,
    refresh,
  } = useRequest(() => fetchMarkdownAsText(markdownUrl!), {
    ready,
    refreshDeps: [markdownUrl, enabled],
  });

  const errorMessage = error == null ? null : error instanceof Error ? error.message : MARKDOWN_LOAD_ERROR;

  return { text, loading, error: errorMessage, reload: refresh };
}
