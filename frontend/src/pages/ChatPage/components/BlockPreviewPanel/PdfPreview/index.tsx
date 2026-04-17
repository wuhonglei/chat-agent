import type { PdfBlock } from "@/interfaces/contentBlock";
import { downloadFileByUrl } from "@/utils";
import { CloseOutlined, DownloadOutlined } from "@ant-design/icons";
import { Button, Spin, Tooltip, Typography } from "antd";
import PdfWorker from "pdfjs-dist/build/pdf.worker.min.mjs?worker";
import React, { useMemo, useRef } from "react";
import { Document, Page, pdfjs } from "react-pdf";
import "react-pdf/dist/Page/AnnotationLayer.css";
import "react-pdf/dist/Page/TextLayer.css";
import { usePdfPageWidth, usePdfPreviewState } from "./hooks";
import PdfDocumentErrorBoundary from "./PdfDocumentErrorBoundary";

pdfjs.GlobalWorkerOptions.workerPort = new PdfWorker();

export interface PdfBlockPreviewPanelProps {
  block: PdfBlock;
  onClose: () => void;
}

const PdfBlockPreviewPanel: React.FC<PdfBlockPreviewPanelProps> = ({ block, onClose }) => {
  const { url: pdfUrl, name: pdfName } = block;
  const contentRef = useRef<HTMLDivElement>(null);

  const { pageWidth, paddingX } = usePdfPageWidth(contentRef);
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
      <header className="flex h-[60px] shrink-0 items-center justify-between gap-2 border-b border-(--ant-color-border-secondary) bg-(--ant-color-bg-container) px-3">
        <Typography.Text type="secondary">共 {numPages > 0 ? numPages : "-"} 页</Typography.Text>
        <div className="flex items-center gap-1">
          <Tooltip title="下载 PDF">
            <Button
              type="text"
              onClick={handleDownloadPdf}
              icon={<DownloadOutlined />}
              disabled={Boolean(loadErrorMessage)}
            />
          </Tooltip>
          <Button type="text" onClick={onClose} icon={<CloseOutlined />} />
        </div>
      </header>
      <div ref={contentRef} className="flex-1 min-h-0 overflow-auto">
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
                <div className="p-5 space-y-4 shadow-lg" style={{ paddingLeft: paddingX, paddingRight: paddingX }}>
                  {pageNumbers.map(currentPageNumber => (
                    <Page
                      width={pageWidth}
                      key={currentPageNumber}
                      pageNumber={currentPageNumber}
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

export default React.memo(PdfBlockPreviewPanel);
