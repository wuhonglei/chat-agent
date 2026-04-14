import { downloadFileByUrl } from "@/utils";
import { CloseOutlined, DownloadOutlined } from "@ant-design/icons";
import { Button, Spin, Typography } from "antd";
import PdfWorker from "pdfjs-dist/build/pdf.worker.min.mjs?worker";
import React, { useEffect, useMemo, useRef, useState } from "react";
import { Document, Page, pdfjs } from "react-pdf";
import "react-pdf/dist/Page/AnnotationLayer.css";
import "react-pdf/dist/Page/TextLayer.css";
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

  useEffect(() => {
    setNumPages(0);
    setIsDocumentLoaded(false);
    setHasRenderedFirstPage(false);
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
        <Document
          className="w-full"
          file={pdfUrl}
          onLoadSuccess={({ numPages: loadedPages }) => {
            setNumPages(loadedPages);
            setIsDocumentLoaded(true);
          }}
          onLoadError={() => {
            setNumPages(0);
            setIsDocumentLoaded(false);
            setHasRenderedFirstPage(false);
          }}
          loading={<div className="w-full py-8 text-center text-(--ant-color-text-tertiary)">PDF 加载中...</div>}
          noData={<div className="w-full py-8 text-center text-(--ant-color-text-tertiary)">暂无可预览 PDF</div>}
          error={<div className="w-full py-8 text-center text-(--ant-color-error)">PDF 加载失败，请重试</div>}
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
      </div>
    </section>
  );
};

export default React.memo(PdfPreviewPanel);
