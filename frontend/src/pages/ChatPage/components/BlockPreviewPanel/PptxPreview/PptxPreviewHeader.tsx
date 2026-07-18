import { CloseOutlined, DownloadOutlined } from "@ant-design/icons";
import { Button, Segmented, Tooltip, Typography } from "antd";
import React from "react";

export type PreviewMode = "document" | "markdown";

export interface PptxPreviewHeaderProps {
  hasMarkdown: boolean;
  previewMode: PreviewMode;
  onPreviewModeChange: (mode: PreviewMode) => void;
  downloadDisabled: boolean;
  onDownload: () => void;
  onClose: () => void;
}

const PptxPreviewHeader: React.FC<PptxPreviewHeaderProps> = ({
  hasMarkdown,
  previewMode,
  onPreviewModeChange,
  downloadDisabled,
  onDownload,
  onClose,
}) => {
  const downloadTitle = previewMode === "markdown" ? "下载 Markdown" : "下载 PowerPoint";

  return (
    <header className="flex h-[60px] shrink-0 items-center justify-between gap-2 border-b border-(--ant-color-border-secondary) bg-(--ant-color-bg-container) px-3">
      <div className="flex min-w-0 flex-1 items-center gap-3">
        {hasMarkdown ? (
          <Segmented<PreviewMode>
            size="small"
            value={previewMode}
            onChange={onPreviewModeChange}
            options={[
              { label: "文档", value: "document" },
              { label: "Markdown", value: "markdown" },
            ]}
          />
        ) : null}
        <Typography.Text type="secondary">
          {previewMode === "markdown" ? "Markdown 预览" : "PowerPoint 预览"}
        </Typography.Text>
      </div>
      <div className="flex items-center gap-1">
        <Tooltip title={downloadTitle}>
          <Button type="text" onClick={onDownload} icon={<DownloadOutlined />} disabled={downloadDisabled} />
        </Tooltip>
        <Button type="text" onClick={onClose} icon={<CloseOutlined />} />
      </div>
    </header>
  );
};

export default React.memo(PptxPreviewHeader);
