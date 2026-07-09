import type { PreviewableBlock } from "@/interfaces/contentBlock";
import React from "react";
import CodeExecPreviewPanel from "./CodeExecPreview";
import DocxBlockPreviewPanel from "./DocxPreview";
import ExcelBlockPreviewPanel from "./ExcelPreview";
import HtmlBlockPreviewPanel from "./HtmlPreview";
import MarkdownBlockPreviewPanel from "./MarkdownPreview";
import PdfBlockPreviewPanel from "./PdfPreview";
import PptxBlockPreviewPanel from "./PptxPreview";
import ProjectPreviewPanel from "./ProjectPreview";
import TextFileBlockPreviewPanel from "./TextFilePreview";

export interface BlockPreviewPanelProps {
  width: number;
  block: PreviewableBlock;
  onClose: () => void;
}

const BlockPreviewPanel: React.FC<BlockPreviewPanelProps> = ({ width, block, onClose }) => {
  switch (block.type) {
    case "pdf":
      return <PdfBlockPreviewPanel width={width} block={block} onClose={onClose} />;
    case "excel":
      return <ExcelBlockPreviewPanel width={width} block={block} onClose={onClose} />;
    case "docx":
      return <DocxBlockPreviewPanel width={width} block={block} onClose={onClose} />;
    case "pptx":
      return <PptxBlockPreviewPanel width={width} block={block} onClose={onClose} />;
    case "markdown":
      return <MarkdownBlockPreviewPanel width={width} block={block} onClose={onClose} />;
    case "text_file":
      return <TextFileBlockPreviewPanel width={width} block={block} onClose={onClose} />;
    case "html":
      return <HtmlBlockPreviewPanel width={width} block={block} onClose={onClose} />;
    case "code_exec":
      return <CodeExecPreviewPanel width={width} block={block} onClose={onClose} />;
    case "project":
      return <ProjectPreviewPanel width={width} block={block} onClose={onClose} />;
    default: {
      const _exhaustive: never = block;
      return _exhaustive;
    }
  }
};

export default React.memo(BlockPreviewPanel);
