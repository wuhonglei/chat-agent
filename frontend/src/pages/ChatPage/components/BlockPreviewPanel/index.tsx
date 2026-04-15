import type { PreviewableBlock } from "@/interfaces/contentBlock";
import React from "react";
import HtmlBlockPreviewPanel from "./HtmlBlockPreviewPanel";
import PdfBlockPreviewPanel from "./PdfBlockPreviewPanel";

export interface BlockPreviewPanelProps {
  block: PreviewableBlock;
  isSmallScreen: boolean;
  onClose: () => void;
}

const BlockPreviewPanel: React.FC<BlockPreviewPanelProps> = ({ block, isSmallScreen, onClose }) => {
  switch (block.type) {
    case "pdf":
      return <PdfBlockPreviewPanel block={block} isSmallScreen={isSmallScreen} onClose={onClose} />;
    case "html":
      return <HtmlBlockPreviewPanel block={block} isSmallScreen={isSmallScreen} onClose={onClose} />;
    default: {
      const _exhaustive: never = block;
      return _exhaustive;
    }
  }
};

export default React.memo(BlockPreviewPanel);
