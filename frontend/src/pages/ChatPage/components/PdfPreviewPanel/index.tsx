import { CloseOutlined } from "@ant-design/icons";
import { Button, Typography } from "antd";
import React, { useMemo, useRef, useState } from "react";
import { Document, Page, pdfjs } from "react-pdf";
import "react-pdf/dist/Page/AnnotationLayer.css";
import "react-pdf/dist/Page/TextLayer.css";
import { usePdfPageWidth, usePdfPreviewAutoCloseOnSmallScreen } from "./hooks";

pdfjs.GlobalWorkerOptions.workerSrc = new URL("pdfjs-dist/build/pdf.worker.min.mjs", import.meta.url).toString();

export interface PdfPreviewPanelProps {
  pdfUrl: string;
  isSmallScreen: boolean;
  onClose: () => void;
}

const PdfPreviewPanel: React.FC<PdfPreviewPanelProps> = ({ pdfUrl, isSmallScreen, onClose }) => {
  const [numPages, setNumPages] = useState(0);
  const contentRef = useRef<HTMLDivElement>(null);

  usePdfPreviewAutoCloseOnSmallScreen({
    isSmallScreen,
    hasPreviewingPdf: true,
    onClose,
  });

  const pageWidth = usePdfPageWidth(contentRef);

  const pageNumbers = useMemo(() => Array.from({ length: numPages }, (_, index) => index + 1), [numPages]);

  return (
    <section className="h-full min-h-0 flex flex-col border-l border-(--ant-color-border-secondary) bg-(--ant-color-bg-layout)">
      <header className="flex items-center justify-between gap-2 px-3 py-2 border-b border-(--ant-color-border-secondary) bg-(--ant-color-bg-container)">
        <Typography.Text type="secondary">共 {numPages > 0 ? numPages : "-"} 页</Typography.Text>
        <Button type="text" onClick={onClose} icon={<CloseOutlined />}></Button>
      </header>
      <div ref={contentRef} className="flex-1 min-h-0 overflow-auto p-3">
        <Document
          file={pdfUrl}
          onLoadSuccess={({ numPages: loadedPages }) => {
            setNumPages(loadedPages);
          }}
          loading={<div className="w-full py-8 text-center text-(--ant-color-text-tertiary)">PDF 加载中...</div>}
          noData={<div className="w-full py-8 text-center text-(--ant-color-text-tertiary)">暂无可预览 PDF</div>}
          error={<div className="w-full py-8 text-center text-(--ant-color-error)">PDF 加载失败，请重试</div>}
          className="w-full"
        >
          <div className="space-y-3">
            {pageNumbers.map(currentPageNumber => (
              <Page key={currentPageNumber} pageNumber={currentPageNumber} width={pageWidth} />
            ))}
          </div>
        </Document>
      </div>
    </section>
  );
};

export default React.memo(PdfPreviewPanel);
