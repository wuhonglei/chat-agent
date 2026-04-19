import { CloseOutlined, DownloadOutlined } from "@ant-design/icons";
import { Button, Segmented, Tooltip, Typography } from "antd";
import React from "react";

export type PreviewMode = "pdf" | "markdown";

export interface PdfPreviewHeaderProps {
  hasMarkdown: boolean;
  previewMode: PreviewMode;
  onPreviewModeChange: (mode: PreviewMode) => void;
  numPages: number;
  /** PDF 失败或 Markdown 预览失败时禁用下载 */
  downloadDisabled: boolean;
  onDownload: () => void;
  onClose: () => void;
}

const PdfPreviewHeader: React.FC<PdfPreviewHeaderProps> = ({
  hasMarkdown,
  previewMode,
  onPreviewModeChange,
  numPages,
  downloadDisabled,
  onDownload,
  onClose,
}) => {
  const downloadTitle = previewMode === "markdown" ? "下载 Markdown" : "下载 PDF";

  return (
    <header className="flex h-[60px] shrink-0 items-center justify-between gap-2 border-b border-(--ant-color-border-secondary) bg-(--ant-color-bg-container) px-3">
      <div className="flex min-w-0 flex-1 items-center gap-3">
        {hasMarkdown ? (
          <Segmented<PreviewMode>
            size="small"
            value={previewMode}
            onChange={onPreviewModeChange}
            options={[
              { label: "PDF", value: "pdf" },
              { label: "Markdown", value: "markdown" },
            ]}
          />
        ) : null}
        {previewMode === "pdf" ? (
          <Typography.Text type="secondary">共 {numPages > 0 ? numPages : "-"} 页</Typography.Text>
        ) : (
          <Typography.Text type="secondary">Markdown 预览</Typography.Text>
        )}
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

export default React.memo(PdfPreviewHeader);
