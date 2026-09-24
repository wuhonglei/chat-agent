import { Segmented, Typography } from "antd";
import React, { useState } from "react";
import type { HtmlViewMode } from "../../utils/htmlPreview";

const FileTitleBar: React.FC<{ title: string; extra?: React.ReactNode }> = ({ title, extra }) => {
  if (!extra) {
    return (
      <Typography.Text
        type="secondary"
        className="px-3 py-2 border-b border-(--ant-color-border-secondary)"
      >
        {title}
      </Typography.Text>
    );
  }

  return (
    <div className="flex shrink-0 items-center justify-between gap-2 border-b border-(--ant-color-border-secondary) px-3 py-2">
      <Typography.Text type="secondary" className="min-w-0 truncate">
        {title}
      </Typography.Text>
      {extra}
    </div>
  );
};

const PreviewModeShell: React.FC<{
  title: string;
  defaultMode?: HtmlViewMode;
  preview: React.ReactNode;
  source: React.ReactNode;
}> = ({ title, defaultMode = "preview", preview, source }) => {
  const [userViewMode, setUserViewMode] = useState<HtmlViewMode | null>(null);
  const viewMode = userViewMode ?? defaultMode;

  return (
    <div className="h-full min-h-0 flex flex-col">
      <FileTitleBar
        title={title}
        extra={
          <Segmented<HtmlViewMode>
            size="small"
            value={viewMode}
            onChange={setUserViewMode}
            options={[
              { label: "预览", value: "preview" },
              { label: "源码", value: "source" },
            ]}
          />
        }
      />
      {viewMode === "preview" ? preview : source}
    </div>
  );
};

export { FileTitleBar };
export default PreviewModeShell;
