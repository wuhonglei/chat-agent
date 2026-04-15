import type { PreviewableBlock } from "@/interfaces/contentBlock";
import { EyeOutlined } from "@ant-design/icons";
import { Actions } from "@ant-design/x";
import { Button } from "antd";
import React from "react";

function createHtmlPreviewBlockId() {
  return `html_preview_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`;
}

export interface HtmlPreviewHeaderProps {
  language: string;
  code: string;
  openPreview: (block: PreviewableBlock) => void;
}

const HtmlPreviewHeader: React.FC<HtmlPreviewHeaderProps> = ({ language, code, openPreview }) => {
  return (
    <>
      <span className="text-(--ant-color-text-secondary)">{language}</span>
      <div className="flex shrink-0 items-center gap-1">
        <Button
          type="text"
          size="small"
          className="px-1!"
          icon={<EyeOutlined />}
          onClick={() =>
            openPreview({
              id: createHtmlPreviewBlockId(),
              type: "html",
              content: code,
            })
          }
        >
          预览
        </Button>
        <Actions.Copy text={code} />
      </div>
    </>
  );
};

export default React.memo(HtmlPreviewHeader);
