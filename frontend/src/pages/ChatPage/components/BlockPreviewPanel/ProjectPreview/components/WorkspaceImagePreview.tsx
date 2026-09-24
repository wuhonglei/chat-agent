import { Alert, Empty, Spin, Typography } from "antd";
import React from "react";

export interface WorkspaceImagePreviewProps {
  title: string;
  url: string | null;
  loading: boolean;
  error: string | null;
}

const WorkspaceImagePreview: React.FC<WorkspaceImagePreviewProps> = ({ title, url, loading, error }) => {
  return (
    <div className="h-full min-h-0 flex flex-col">
      <Typography.Text type="secondary" className="px-3 py-2 border-b border-(--ant-color-border-secondary)">
        {title}
      </Typography.Text>
      <div className="min-h-0 flex flex-1 items-center justify-center overflow-auto bg-(--ant-color-fill-quaternary) p-4">
        {loading ? (
          <Spin />
        ) : error ? (
          <Alert type="error" showIcon message={error} className="max-w-md" />
        ) : url ? (
          <img src={url} alt={title} className="max-h-full max-w-full object-contain" />
        ) : (
          <Empty description="暂无可预览内容" />
        )}
      </div>
    </div>
  );
};

export default React.memo(WorkspaceImagePreview);
