import type { HtmlBlock } from "@/interfaces/contentBlock";
import { CloseOutlined } from "@ant-design/icons";
import { Button, Typography } from "antd";
import React from "react";
import { usePdfPreviewAutoCloseOnSmallScreen } from "./hooks";

export interface HtmlBlockPreviewPanelProps {
  block: HtmlBlock;
  isSmallScreen: boolean;
  onClose: () => void;
}

const HtmlBlockPreviewPanel: React.FC<HtmlBlockPreviewPanelProps> = ({ block, isSmallScreen, onClose }) => {
  usePdfPreviewAutoCloseOnSmallScreen({ isSmallScreen, onClose });

  return (
    <section className="h-full min-h-0 flex flex-col border-l border-(--ant-color-border-secondary) bg-(--ant-color-bg-layout)">
      <header className="flex items-center justify-between gap-2 px-3 py-2 border-b border-(--ant-color-border-secondary) bg-(--ant-color-bg-container)">
        <Typography.Text type="secondary">HTML 预览</Typography.Text>
        <Button type="text" onClick={onClose} icon={<CloseOutlined />} />
      </header>
      <div className="flex min-h-0 flex-1 flex-col p-3">
        <iframe
          title="HTML 预览"
          className="h-full min-h-[280px] w-full flex-1 rounded border border-(--ant-color-border-secondary) bg-white"
          srcDoc={block.content}
          sandbox=""
        />
      </div>
    </section>
  );
};

export default React.memo(HtmlBlockPreviewPanel);
