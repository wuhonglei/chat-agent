import { DownloadOutlined, ZoomInOutlined, ZoomOutOutlined } from "@ant-design/icons";
import { Actions } from "@ant-design/x";
import { Button, Segmented, Tooltip } from "antd";
import React, { useMemo, useState } from "react";
import CodeHighlighter from "./CodeHighlighter";

const SVG_MARKUP = /<svg[\s>]/i;
const MIN_SCALE = 0.5;
const MAX_SCALE = 3;
const SCALE_STEP = 0.2;

type SvgViewMode = "image" | "code";

function toSvgDataUrl(content: string): string {
  return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(content)}`;
}

function downloadSvg(code: string) {
  const blob = new Blob([code], { type: "image/svg+xml;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `${Date.now()}.svg`;
  link.click();
  URL.revokeObjectURL(url);
}

const SvgBlock: React.FC<{ code: string }> = ({ code }) => {
  const [viewMode, setViewMode] = useState<SvgViewMode>("image");
  const [scale, setScale] = useState(1);
  const src = useMemo(() => toSvgDataUrl(code), [code]);
  const canPreview = SVG_MARKUP.test(code);

  const imageActions = useMemo(
    () => [
      {
        key: "zoomIn",
        icon: <ZoomInOutlined />,
        label: "放大",
        onItemClick: () => setScale((prev) => Math.min(prev + SCALE_STEP, MAX_SCALE)),
      },
      {
        key: "zoomOut",
        icon: <ZoomOutOutlined />,
        label: "缩小",
        onItemClick: () => setScale((prev) => Math.max(prev - SCALE_STEP, MIN_SCALE)),
      },
      {
        key: "zoomReset",
        actionRender: () => (
          <Tooltip title="重置">
            <Button type="text" size="small" onClick={() => setScale(1)}>
              重置
            </Button>
          </Tooltip>
        ),
      },
      {
        key: "download",
        icon: <DownloadOutlined />,
        label: "下载",
        onItemClick: () => downloadSvg(code),
      },
    ],
    [code],
  );

  if (!canPreview) {
    return <CodeHighlighter lang="svg">{code}</CodeHighlighter>;
  }

  return (
    <div className="my-2 overflow-hidden rounded-md">
      <div className="flex items-center justify-between bg-(--ant-color-fill-content) px-3 py-2">
        <Segmented<SvgViewMode>
          value={viewMode}
          onChange={setViewMode}
          options={[
            { label: "图片", value: "image" },
            { label: "代码", value: "code" },
          ]}
        />
        {viewMode === "image" ? <Actions items={imageActions} /> : null}
      </div>
      {viewMode === "image" ? (
        <div className="flex h-100 min-h-0 items-center justify-center overflow-hidden border border-t-0 border-(--ant-color-fill-content) bg-white">
          <img
            src={src}
            alt="SVG"
            className="max-h-full min-h-0 max-w-full object-contain transition-transform duration-100"
            style={{ transform: `scale(${scale})`, transformOrigin: "center" }}
            onError={() => setViewMode("code")}
          />
        </div>
      ) : (
        <div className="h-100 overflow-auto border border-t-0 border-(--ant-color-fill-content) bg-white">
          <CodeHighlighter lang="svg" header={null} maxHeight={null}>
            {code}
          </CodeHighlighter>
        </div>
      )}
    </div>
  );
};

export default SvgBlock;
