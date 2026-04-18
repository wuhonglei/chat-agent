import classNames from "classnames";
import React from "react";
import { getPreviewPaddingX } from "./previewLayout";

export interface PreviewScrollBodyProps {
  /** 用于计算左右 padding 的容器宽度（px），通常来自侧栏宽度或内容区测量值 */
  width: number;
  className?: string;
  children: React.ReactNode;
}

/**
 * 预览区统一滚动内容容器：根据 width 计算左右对称 padding，避免在各处单独写 p-* 与内联 padding。
 */
const PreviewScrollBody: React.FC<PreviewScrollBodyProps> = ({ width, className, children }) => {
  const paddingX = getPreviewPaddingX(width);

  return (
    <div className={classNames("py-5", className)} style={{ paddingLeft: paddingX, paddingRight: paddingX }}>
      {children}
    </div>
  );
};

export default React.memo(PreviewScrollBody);
