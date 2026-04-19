import type { HtmlBlock } from "@/interfaces/contentBlock";
import { downloadHtmlContent } from "@/utils";
import { CloseOutlined, DownloadOutlined } from "@ant-design/icons";
import { Button, Tooltip, Typography } from "antd";
import React from "react";

export interface HtmlBlockPreviewPanelProps {
  width: number;
  block: HtmlBlock;
  onClose: () => void;
}

const HtmlBlockPreviewPanel: React.FC<HtmlBlockPreviewPanelProps> = ({ block, onClose }) => {
  const handleDownloadHtml = () => {
    downloadHtmlContent(block.content);
  };

  return (
    <section className="h-full min-h-0 flex flex-col border-l border-(--ant-color-border-secondary) bg-(--ant-color-bg-layout)">
      <header className="flex h-[60px] shrink-0 items-center justify-between gap-2 border-b border-(--ant-color-border-secondary) bg-(--ant-color-bg-container) px-3">
        <Typography.Text type="secondary">HTML 预览</Typography.Text>
        <div className="flex items-center gap-1">
          <Tooltip title="下载 HTML">
            <Button
              type="text"
              onClick={handleDownloadHtml}
              icon={<DownloadOutlined />}
              disabled={!block.content.trim()}
            />
          </Tooltip>
          <Button type="text" onClick={onClose} icon={<CloseOutlined />} />
        </div>
      </header>
      <div className="flex min-h-0 flex-1 flex-col">
        <iframe
          sandbox=""
          title="HTML 预览"
          srcDoc={block.content}
          className="h-full min-h-[280px] w-full flex-1 rounded border border-(--ant-color-border-secondary) bg-white"
        />
      </div>
    </section>
  );
};

export default React.memo(HtmlBlockPreviewPanel);
