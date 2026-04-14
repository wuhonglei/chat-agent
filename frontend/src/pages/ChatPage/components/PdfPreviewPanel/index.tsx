import { CloseOutlined } from "@ant-design/icons";
import { useThrottleFn } from "ahooks";
import { Button } from "antd";
import React, { useRef, useState } from "react";
import { Document, Page, pdfjs } from "react-pdf";
import "react-pdf/dist/Page/AnnotationLayer.css";
import "react-pdf/dist/Page/TextLayer.css";
import { usePdfPageWidth, usePdfPreviewAutoCloseOnSmallScreen } from "./hooks";
import PaginationControl from "./PaginationControl";

pdfjs.GlobalWorkerOptions.workerSrc = new URL("pdfjs-dist/build/pdf.worker.min.mjs", import.meta.url).toString();

export interface PdfPreviewPanelProps {
  pdfUrl: string;
  isSmallScreen: boolean;
  onClose: () => void;
}

const PdfPreviewPanel: React.FC<PdfPreviewPanelProps> = ({ pdfUrl, isSmallScreen, onClose }) => {
  const [numPages, setNumPages] = useState(0);
  const [pageNumber, setPageNumber] = useState(1);
  const contentRef = useRef<HTMLDivElement>(null);

  usePdfPreviewAutoCloseOnSmallScreen({
    isSmallScreen,
    hasPreviewingPdf: true,
    onClose,
  });

  const pageWidth = usePdfPageWidth(contentRef);

  const { run: onWheelThrottled } = useThrottleFn(
    (event: React.WheelEvent<HTMLDivElement>) => {
      if (numPages <= 0 || event.deltaY === 0) {
        return;
      }

      const isScrollDown = event.deltaY > 0;
      const nextPage = isScrollDown ? Math.min(pageNumber + 1, numPages) : Math.max(pageNumber - 1, 1);

      if (nextPage === pageNumber) {
        return;
      }

      event.preventDefault();
      setPageNumber(nextPage);
    },
    { wait: 500 }
  );

  return (
    <section className="h-full min-h-0 flex flex-col border-l border-(--ant-color-border-secondary) bg-(--ant-color-bg-layout)">
      <header className="flex items-center justify-between gap-2 px-3 py-2 border-b border-(--ant-color-border-secondary) bg-(--ant-color-bg-container)">
        <PaginationControl numPages={numPages} pageNumber={pageNumber} onPageNumberChange={setPageNumber} />
        <Button type="text" onClick={onClose} icon={<CloseOutlined />}></Button>
      </header>
      <div ref={contentRef} className="flex-1 min-h-0 overflow-auto p-3" onWheel={onWheelThrottled}>
        <Document
          file={pdfUrl}
          onLoadSuccess={({ numPages: loadedPages }) => {
            setNumPages(loadedPages);
            setPageNumber(1);
          }}
          loading={<div className="w-full py-8 text-center text-(--ant-color-text-tertiary)">PDF 加载中...</div>}
          noData={<div className="w-full py-8 text-center text-(--ant-color-text-tertiary)">暂无可预览 PDF</div>}
          error={<div className="w-full py-8 text-center text-(--ant-color-error)">PDF 加载失败，请重试</div>}
          className="w-full"
        >
          <Page pageNumber={pageNumber} width={pageWidth} />
        </Document>
      </div>
    </section>
  );
};

export default React.memo(PdfPreviewPanel);
