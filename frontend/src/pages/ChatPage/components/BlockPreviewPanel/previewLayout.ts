/** 预览区滚动内容的最小 PDF 页宽（px） */
export const MIN_PREVIEW_PAGE_WIDTH = 240;

/**
 * 根据预览容器宽度（px）计算左右对称 padding，与 PDF 页宽计算共用同一套规则。
 */
export function getPreviewPaddingX(containerWidth: number): number {
  if (containerWidth >= 880) return 80;
  if (containerWidth >= 640) return 48;
  if (containerWidth >= 480) return 32;
  return 16;
}

/** 根据 layoutWidth（px）得到 react-pdf Page 的 width；无有效宽度时回退 360 */
export function computePdfPageWidth(layoutWidth: number): number {
  if (!layoutWidth) {
    return 360;
  }
  const paddingX = getPreviewPaddingX(layoutWidth);
  return Math.max(layoutWidth - paddingX * 2, MIN_PREVIEW_PAGE_WIDTH);
}
