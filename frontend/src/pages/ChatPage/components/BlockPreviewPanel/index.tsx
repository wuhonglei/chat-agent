import type { PreviewableBlock } from "@/interfaces/contentBlock";
import React from "react";
import CodeExecPreviewPanel from "./CodeExecPreview";
import HtmlBlockPreviewPanel from "./HtmlPreview";
import MarkdownBlockPreviewPanel from "./MarkdownPreview";
import PdfBlockPreviewPanel from "./PdfPreview";
import ProjectPreviewPanel from "./ProjectPreview";

export interface BlockPreviewPanelProps {
  width: number;
  block: PreviewableBlock;
  onClose: () => void;
}

const BlockPreviewPanel: React.FC<BlockPreviewPanelProps> = ({ width, block, onClose }) => {
  switch (block.type) {
    case "pdf":
      return <PdfBlockPreviewPanel width={width} block={block} onClose={onClose} />;
    case "markdown":
      return <MarkdownBlockPreviewPanel width={width} block={block} onClose={onClose} />;
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
