import type { PdfBlock } from "@/interfaces/contentBlock";
import MarkdownContainer from "@/pages/ChatPage/components/MarkdownContainer";
import { downloadFileByUrl } from "@/utils";
import { Button, Spin, Typography } from "antd";
import PdfWorker from "pdfjs-dist/build/pdf.worker.min.mjs?worker";
import React, { useEffect, useMemo, useRef, useState } from "react";
import { Document, Page, pdfjs } from "react-pdf";
import "react-pdf/dist/Page/AnnotationLayer.css";
import "react-pdf/dist/Page/TextLayer.css";
import { useMarkdownPreviewContent, usePdfPageWidth, usePdfPreviewState } from "./hooks";
import PdfDocumentErrorBoundary from "./PdfDocumentErrorBoundary";
import PdfPreviewHeader, { type PreviewMode } from "./PdfPreviewHeader";

pdfjs.GlobalWorkerOptions.workerPort = new PdfWorker();

export interface PdfBlockPreviewPanelProps {
  block: PdfBlock;
  onClose: () => void;
}

const PdfBlockPreviewPanel: React.FC<PdfBlockPreviewPanelProps> = ({ block, onClose }) => {
  const { url: pdfUrl, name: pdfName, markdown: markdownBlock } = block;
  const contentRef = useRef<HTMLDivElement>(null);
  const hasMarkdown = Boolean(markdownBlock?.url);
  const [previewMode, setPreviewMode] = useState<PreviewMode>("pdf");

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

  const markdownUrl = markdownBlock?.url;
  const isMarkdownView = hasMarkdown && previewMode === "markdown";
  const {
    text: markdownText,
    loading: markdownLoading,
    error: markdownError,
    reload: reloadMarkdown,
  } = useMarkdownPreviewContent(markdownUrl, isMarkdownView);

  useEffect(() => {
    setPreviewMode("pdf");
  }, [block.id, pdfUrl]);

  const pageNumbers = useMemo(() => Array.from({ length: numPages }, (_, index) => index + 1), [numPages]);

  const errorMessage = loadErrorMessage || "PDF 加载失败，请重试";
  const documentKey = `${pdfUrl}-${reloadToken}`;

  const handleDownload = () => {
    if (previewMode === "markdown" && markdownBlock?.url) {
      downloadFileByUrl(markdownBlock.url, markdownBlock.name?.trim() || "document.md");
    } else {
      downloadFileByUrl(pdfUrl, pdfName?.trim() || "document.pdf");
    }
  };

  const downloadDisabled = previewMode === "markdown" ? Boolean(markdownError) : Boolean(loadErrorMessage);
  const errorFallback = (
    <div className="w-full py-8 text-center text-(--ant-color-error)">
      <Typography.Paragraph className="mb-3!">{errorMessage}</Typography.Paragraph>
      <Button type="default" onClick={handleRetryPreview}>
        重新加载
      </Button>
    </div>
  );

  const markdownErrorFallback = markdownError ? (
    <div className="w-full py-8 text-center text-(--ant-color-error)">
      <Typography.Paragraph className="mb-3!">{markdownError}</Typography.Paragraph>
      <Button type="default" onClick={reloadMarkdown}>
        重新加载
      </Button>
    </div>
  ) : null;

  return (
    <section className="h-full min-h-0 flex flex-col border-l border-(--ant-color-border-secondary) bg-(--ant-color-bg-layout)">
      <PdfPreviewHeader
        onClose={onClose}
        numPages={numPages}
        hasMarkdown={hasMarkdown}
        previewMode={previewMode}
        onDownload={handleDownload}
        onPreviewModeChange={setPreviewMode}
        downloadDisabled={downloadDisabled}
      />
      <div ref={contentRef} className="flex-1 min-h-0 overflow-auto">
        {isMarkdownView ? (
          <div className="p-5">
            {markdownLoading ? (
              <div className="flex w-full justify-center py-12">
                <Spin />
              </div>
            ) : markdownErrorFallback ? (
              markdownErrorFallback
            ) : (
              <MarkdownContainer className="w-full text-base bg-white p-4">{markdownText}</MarkdownContainer>
            )}
          </div>
        ) : loadErrorMessage ? (
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
