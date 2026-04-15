import { downloadFileByUrl } from "@/utils";
import { CloseOutlined, DownloadOutlined } from "@ant-design/icons";
import { Button, Spin, Typography } from "antd";
import PdfWorker from "pdfjs-dist/build/pdf.worker.min.mjs?worker";
import React, { useMemo, useRef } from "react";
import { Document, Page, pdfjs } from "react-pdf";
import "react-pdf/dist/Page/AnnotationLayer.css";
import "react-pdf/dist/Page/TextLayer.css";
import PdfDocumentErrorBoundary from "./PdfDocumentErrorBoundary";
import { usePdfPageWidth, usePdfPreviewAutoCloseOnSmallScreen, usePdfPreviewState } from "./hooks";

pdfjs.GlobalWorkerOptions.workerPort = new PdfWorker();

export interface BlockPreviewPanelProps {
  pdfUrl: string;
  pdfName?: string;
  isSmallScreen: boolean;
  onClose: () => void;
}

const BlockPreviewPanel: React.FC<BlockPreviewPanelProps> = ({ pdfUrl, pdfName, isSmallScreen, onClose }) => {
  const contentRef = useRef<HTMLDivElement>(null);

  usePdfPreviewAutoCloseOnSmallScreen({ isSmallScreen, onClose });

  const pageWidth = usePdfPageWidth(contentRef);
  const {
    numPages,
    loadErrorMessage,
    reloadToken,
    isPreviewReady,
    handleDocumentLoadSuccess,
    handlePdfLoadError,
    handleRetryPreview,
    markFirstPageAsRendered,
  } = usePdfPreviewState(pdfUrl);

  const pageNumbers = useMemo(() => Array.from({ length: numPages }, (_, index) => index + 1), [numPages]);

  const errorMessage = loadErrorMessage || "PDF 加载失败，请重试";
  const documentKey = `${pdfUrl}-${reloadToken}`;

  const handleDownloadPdf = () => {
    downloadFileByUrl(pdfUrl, pdfName?.trim() || "document.pdf");
  };
  const errorFallback = (
    <div className="w-full py-8 text-center text-(--ant-color-error)">
      <Typography.Paragraph className="mb-3!">{errorMessage}</Typography.Paragraph>
      <Button type="default" onClick={handleRetryPreview}>
        重新加载
      </Button>
    </div>
  );

  return (
    <section className="h-full min-h-0 flex flex-col border-l border-(--ant-color-border-secondary) bg-(--ant-color-bg-layout)">
      <header className="flex items-center justify-between gap-2 px-3 py-2 border-b border-(--ant-color-border-secondary) bg-(--ant-color-bg-container)">
        <Typography.Text type="secondary">共 {numPages > 0 ? numPages : "-"} 页</Typography.Text>
        <div className="flex items-center gap-1">
          <Button
            type="text"
            title="下载 PDF"
            onClick={handleDownloadPdf}
            icon={<DownloadOutlined />}
            disabled={Boolean(loadErrorMessage)}
          />
          <Button type="text" onClick={onClose} icon={<CloseOutlined />}></Button>
        </div>
      </header>
      <div ref={contentRef} className="flex-1 min-h-0 overflow-auto p-3">
        {loadErrorMessage ? (
          errorFallback
        ) : (
          <PdfDocumentErrorBoundary resetKey={documentKey} onError={handlePdfLoadError} fallback={errorFallback}>
            <Document
              key={documentKey}
              className="w-full"
              file={pdfUrl}
              onLoadSuccess={handleDocumentLoadSuccess}
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
                      onRenderSuccess={currentPageNumber === 1 ? markFirstPageAsRendered : undefined}
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

export default React.memo(BlockPreviewPanel);
