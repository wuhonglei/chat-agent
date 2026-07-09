import type { PptxBlock } from "@/interfaces/contentBlock";
import MarkdownContainer from "@/pages/ChatPage/components/MarkdownContainer";
import { downloadFileByUrl } from "@/utils";
import { Button, Spin, Typography } from "antd";
import React, { useEffect, useState } from "react";
import { useMarkdownPreviewContent } from "../PdfPreview/hooks";
import PreviewScrollBody from "../PreviewScrollBody";
import { usePptxDocumentPreview } from "./hooks";
import PptxPreviewHeader, { type PreviewMode } from "./PptxPreviewHeader";

export interface PptxBlockPreviewPanelProps {
  width: number;
  block: PptxBlock;
  onClose: () => void;
}

const PptxBlockPreviewPanel: React.FC<PptxBlockPreviewPanelProps> = ({ width, block, onClose }) => {
  const { url: pptxUrl, name: pptxName, markdown: markdownBlock } = block;
  const layoutWidth = width > 0 ? width : 0;

  const hasMarkdown = Boolean(markdownBlock?.url);
  const [previewMode, setPreviewMode] = useState<PreviewMode>("document");
  const [containerEl, setContainerEl] = useState<HTMLDivElement | null>(null);

  const isMarkdownView = hasMarkdown && previewMode === "markdown";
  const isDocumentView = !isMarkdownView;

  const {
    loading: docLoading,
    error: docError,
    reload: reloadDoc,
  } = usePptxDocumentPreview(pptxUrl, isDocumentView, containerEl, layoutWidth);

  const markdownUrl = markdownBlock?.url;
  const {
    text: markdownText,
    loading: markdownLoading,
    error: markdownError,
    reload: reloadMarkdown,
  } = useMarkdownPreviewContent(markdownUrl, isMarkdownView);

  useEffect(() => {
    setPreviewMode("document");
  }, [block.id, pptxUrl]);

  const handleDownload = () => {
    if (previewMode === "markdown" && markdownBlock?.url) {
      downloadFileByUrl(markdownBlock.url, markdownBlock.name?.trim() || "presentation.md");
    } else {
      downloadFileByUrl(pptxUrl, pptxName?.trim() || "presentation.pptx");
    }
  };

  const downloadDisabled = previewMode === "markdown" ? Boolean(markdownError) : Boolean(docError);

  const documentErrorFallback = docError ? (
    <div className="w-full py-8 text-center text-(--ant-color-error)">
      <Typography.Paragraph className="mb-3!">{docError}</Typography.Paragraph>
      <Button type="default" onClick={reloadDoc}>
        重新加载
      </Button>
    </div>
  ) : null;

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
      <PptxPreviewHeader
        onClose={onClose}
        hasMarkdown={hasMarkdown}
        previewMode={previewMode}
        onDownload={handleDownload}
        onPreviewModeChange={setPreviewMode}
        downloadDisabled={downloadDisabled}
      />
      <div className="flex-1 min-h-0 overflow-auto">
        {isMarkdownView ? (
          <PreviewScrollBody width={layoutWidth}>
            {markdownLoading ? (
              <div className="flex w-full justify-center py-12">
                <Spin />
              </div>
            ) : markdownErrorFallback ? (
              markdownErrorFallback
            ) : (
              <MarkdownContainer className="w-full text-base bg-white p-4">{markdownText}</MarkdownContainer>
            )}
          </PreviewScrollBody>
        ) : (
          <PreviewScrollBody width={layoutWidth}>
            {documentErrorFallback ? (
              documentErrorFallback
            ) : (
              <div className="relative w-full">
                {docLoading ? (
                  <div className="absolute inset-x-0 top-12 z-10 flex justify-center">
                    <Spin />
                  </div>
                ) : null}
                <div ref={setContainerEl} className="pptx-preview-root w-full bg-white" />
              </div>
            )}
          </PreviewScrollBody>
        )}
      </div>
    </section>
  );
};

export default React.memo(PptxBlockPreviewPanel);
