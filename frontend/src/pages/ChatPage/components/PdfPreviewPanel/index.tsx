import { downloadFileByUrl } from "@/utils";
import { CloseOutlined, DownloadOutlined } from "@ant-design/icons";
import { Button, Spin, Typography } from "antd";
import PdfWorker from "pdfjs-dist/build/pdf.worker.min.mjs?worker";
import React, { useEffect, useMemo, useRef, useState } from "react";
import { Document, Page, pdfjs } from "react-pdf";
import "react-pdf/dist/Page/AnnotationLayer.css";
import "react-pdf/dist/Page/TextLayer.css";
import PdfDocumentErrorBoundary from "./PdfDocumentErrorBoundary";
import { usePdfPageWidth, usePdfPreviewAutoCloseOnSmallScreen } from "./hooks";

pdfjs.GlobalWorkerOptions.workerPort = new PdfWorker();

export interface PdfPreviewPanelProps {
  pdfUrl: string;
  pdfName?: string;
  isSmallScreen: boolean;
  onClose: () => void;
}

const PdfPreviewPanel: React.FC<PdfPreviewPanelProps> = ({ pdfUrl, pdfName, isSmallScreen, onClose }) => {
  const [numPages, setNumPages] = useState(0);
  const [isDocumentLoaded, setIsDocumentLoaded] = useState(false);
  const [hasRenderedFirstPage, setHasRenderedFirstPage] = useState(false);
  const [loadErrorMessage, setLoadErrorMessage] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);
  const contentRef = useRef<HTMLDivElement>(null);

  usePdfPreviewAutoCloseOnSmallScreen({
    isSmallScreen,
    hasPreviewingPdf: true,
    onClose,
  });

  const pageWidth = usePdfPageWidth(contentRef);

  const pageNumbers = useMemo(() => Array.from({ length: numPages }, (_, index) => index + 1), [numPages]);
  const isPreviewReady = isDocumentLoaded && hasRenderedFirstPage;
  const handleDownloadPdf = () => {
    downloadFileByUrl(pdfUrl, pdfName?.trim() || "document.pdf");
  };
  const resetPreviewState = () => {
    setNumPages(0);
    setIsDocumentLoaded(false);
    setHasRenderedFirstPage(false);
  };
  const handlePdfLoadError = (error: Error) => {
    resetPreviewState();
    setLoadErrorMessage(error.message || "PDF 加载失败，请重试");
  };
  const handleRetryPreview = () => {
    resetPreviewState();
    setLoadErrorMessage(null);
    setReloadToken(previous => previous + 1);
  };
  const errorFallback = (
    <div className="w-full py-8 text-center text-(--ant-color-error)">
      <Typography.Paragraph className="mb-3!">{loadErrorMessage || "PDF 加载失败，请重试"}</Typography.Paragraph>
      <Button type="default" onClick={handleRetryPreview}>
        重新加载
      </Button>
    </div>
  );

  useEffect(() => {
    resetPreviewState();
    setLoadErrorMessage(null);
    setReloadToken(0);
  }, [pdfUrl]);

  return (
    <section className="h-full min-h-0 flex flex-col border-l border-(--ant-color-border-secondary) bg-(--ant-color-bg-layout)">
      <header className="flex items-center justify-between gap-2 px-3 py-2 border-b border-(--ant-color-border-secondary) bg-(--ant-color-bg-container)">
        <Typography.Text type="secondary">共 {numPages > 0 ? numPages : "-"} 页</Typography.Text>
        <div className="flex items-center gap-1">
          <Button type="text" onClick={handleDownloadPdf} icon={<DownloadOutlined />} title="下载 PDF" />
          <Button type="text" onClick={onClose} icon={<CloseOutlined />}></Button>
        </div>
      </header>
      <div ref={contentRef} className="flex-1 min-h-0 overflow-auto p-3">
        {loadErrorMessage ? (
          errorFallback
        ) : (
          <PdfDocumentErrorBoundary
            resetKey={`${pdfUrl}-${reloadToken}`}
            onError={handlePdfLoadError}
            fallback={errorFallback}
          >
            <Document
              key={`${pdfUrl}-${reloadToken}`}
              className="w-full"
              file={pdfUrl}
              onLoadSuccess={({ numPages: loadedPages }) => {
                setNumPages(loadedPages);
                setIsDocumentLoaded(true);
              }}
              onLoadError={handlePdfLoadError}
              onSourceError={handlePdfLoadError}
              loading={<div className="w-full py-8 text-center text-(--ant-color-text-tertiary)">PDF 加载中...</div>}
              noData={<div className="w-full py-8 text-center text-(--ant-color-text-tertiary)">暂无可预览 PDF</div>}
              error={errorFallback}
            >
              <Spin spinning={numPages > 0 && !isPreviewReady} delay={100}>
                <div className="space-y-3">
                  {pageNumbers.map(currentPageNumber => (
                    <Page
                      key={currentPageNumber}
                      pageNumber={currentPageNumber}
                      width={pageWidth}
                      onRenderSuccess={
                        currentPageNumber === 1
                          ? () => {
                              setHasRenderedFirstPage(true);
                            }
                          : undefined
                      }
                    />
                  ))}
                </div>
              </Spin>
            </Document>
          </PdfDocumentErrorBoundary>
        )}
      </div>
    </section>
  );
};

export default React.memo(PdfPreviewPanel);
