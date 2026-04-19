import type { PreviewableBlock } from "@/interfaces/contentBlock";
import React from "react";
import HtmlBlockPreviewPanel from "./HtmlPreview";
import PdfBlockPreviewPanel from "./PdfPreview";

export interface BlockPreviewPanelProps {
  width: number;
  block: PreviewableBlock;
  onClose: () => void;
}

const BlockPreviewPanel: React.FC<BlockPreviewPanelProps> = ({ width, block, onClose }) => {
  switch (block.type) {
    case "pdf":
      return <PdfBlockPreviewPanel width={width} block={block} onClose={onClose} />;
    case "html":
      return <HtmlBlockPreviewPanel width={width} block={block} onClose={onClose} />;
    default: {
      const _exhaustive: never = block;
      return _exhaustive;
    }
  }
};

export default React.memo(BlockPreviewPanel);
