import { useSize } from "ahooks";
import React, { useEffect, useState } from "react";

const DEFAULT_THRESHOLD = 768;
export const useCollapsed = (
  target: HTMLElement,
  threshold: number = DEFAULT_THRESHOLD
): [boolean, React.Dispatch<React.SetStateAction<boolean>>] => {
  const { width } = useSize(target) || {};
  const [collapsed, setCollapsed] = useState(() =>
    width ? width <= threshold : false
  );

  useEffect(() => {
    // 处理宽度动态变化过程
    setCollapsed(width ? width <= threshold : false);
  }, [width, threshold]);

  return [collapsed, setCollapsed];
};
