import { DownloadOutlined } from "@ant-design/icons";
import { Alert, Button } from "antd";
import React from "react";
import { FileTitleBar } from "./PreviewModeShell";

export interface BinaryFilePreviewProps {
  title: string;
  message: string;
  downloading: boolean;
  onDownload: () => void;
}

const BinaryFilePreview: React.FC<BinaryFilePreviewProps> = ({
  title,
  message,
  downloading,
  onDownload,
}) => {
  return (
    <div className="h-full min-h-0 flex flex-col">
      <FileTitleBar title={title} />
      <div className="flex flex-1 flex-col items-center justify-center gap-3 p-6">
        <Alert type="info" showIcon message={message} className="max-w-md" />
        <Button
          type="primary"
          icon={<DownloadOutlined />}
          loading={downloading}
          onClick={onDownload}
        >
          下载文件
        </Button>
      </div>
    </div>
  );
};

export default BinaryFilePreview;
