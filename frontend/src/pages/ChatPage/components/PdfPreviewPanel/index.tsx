import { CloseOutlined } from "@ant-design/icons";
import { useSize } from "ahooks";
import { Button, Typography } from "antd";
import React, { useMemo, useRef, useState } from "react";
import { Document, Page, pdfjs } from "react-pdf";
import "react-pdf/dist/Page/AnnotationLayer.css";
import "react-pdf/dist/Page/TextLayer.css";
import { usePdfPreviewAutoCloseOnSmallScreen } from "./hooks";

pdfjs.GlobalWorkerOptions.workerSrc = new URL("pdfjs-dist/build/pdf.worker.min.mjs", import.meta.url).toString();

export interface PdfPreviewPanelProps {
  pdfUrl: string;
  pdfName?: string;
  isSmallScreen: boolean;
  onClose: () => void;
}

const PdfPreviewPanel: React.FC<PdfPreviewPanelProps> = ({ pdfUrl, pdfName, isSmallScreen, onClose }) => {
  const [numPages, setNumPages] = useState(0);
  const [pageNumber, setPageNumber] = useState(1);
  const contentRef = useRef<HTMLDivElement>(null);
  const wheelLockRef = useRef(false);
  const contentSize = useSize(contentRef);

  usePdfPreviewAutoCloseOnSmallScreen({
    isSmallScreen,
    hasPreviewingPdf: true,
    onClose,
  });

  const pageWidth = useMemo(() => {
    if (!contentSize?.width) return 360;
    return Math.max(contentSize.width - 24, 240);
  }, [contentSize?.width]);

  const handleWheel = (event: React.WheelEvent<HTMLDivElement>) => {
    if (numPages <= 0 || wheelLockRef.current || event.deltaY === 0) {
      return;
    }

    const isScrollDown = event.deltaY > 0;
    const nextPage = isScrollDown ? Math.min(pageNumber + 1, numPages) : Math.max(pageNumber - 1, 1);

    if (nextPage === pageNumber) {
      return;
    }

    event.preventDefault();
    wheelLockRef.current = true;
    setPageNumber(nextPage);
    window.setTimeout(() => {
      wheelLockRef.current = false;
    }, 180);
  };

  return (
    <section className="h-full min-h-0 flex flex-col border-l border-(--ant-color-border-secondary) bg-(--ant-color-bg-layout)">
      <header className="flex items-center justify-between gap-2 px-3 py-2 border-b border-(--ant-color-border-secondary) bg-(--ant-color-bg-container)">
        <Typography.Text ellipsis={{ tooltip: pdfName }} className="min-w-0">
          {pdfName?.trim() || "PDF 预览"}
        </Typography.Text>
        <Button type="text" onClick={onClose} icon={<CloseOutlined />}></Button>
      </header>
      <div className="flex items-center justify-center px-3 py-2 border-b border-(--ant-color-border-secondary) bg-(--ant-color-bg-container)">
        <Typography.Text type="secondary">{numPages > 0 ? `${pageNumber} / ${numPages}` : "- / -"}</Typography.Text>
      </div>
      <div ref={contentRef} className="flex-1 min-h-0 overflow-auto p-3" onWheel={handleWheel}>
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
