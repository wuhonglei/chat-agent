import type { CodeHighlighterProps } from "@ant-design/x";
import classNames from "classnames";
import { isNil } from 'lodash-es';
import { useEffect, useLayoutEffect, useMemo, useRef, useState, type ReactNode } from "react";

export const CODE_SCROLL_AREA_CLASS = "chat-code-highlighter-code-area";

export function toCssLength(value: number | string): string {
  return typeof value === "number" ? `${value}px` : value;
}

type UseCodeFoldOptions = {
  maxHeight?: number | string | null;
  codeContent: ReactNode;
  classNamesProp?: CodeHighlighterProps["classNames"];
  stylesProp?: CodeHighlighterProps["styles"];
};

export function useCodeFold({ maxHeight, codeContent, classNamesProp, stylesProp }: UseCodeFoldOptions) {
  const rootRef = useRef<HTMLDivElement>(null);
  const [expanded, setExpanded] = useState(false);
  const [overflowing, setOverflowing] = useState(false);

  const maxHeightCss = isNil( maxHeight) ? undefined : toCssLength(maxHeight);

  const mergedClassNames = useMemo(
    () => ({
      ...classNamesProp,
      code: classNames(CODE_SCROLL_AREA_CLASS, classNamesProp?.code),
    }),
    [classNamesProp]
  );

  const mergedStyles = useMemo((): CodeHighlighterProps["styles"] => {
    const codeFromProp = stylesProp?.code ?? {};
    if (!maxHeightCss) {
      return { ...stylesProp, code: codeFromProp };
    }
    return {
      ...stylesProp,
      code: {
        ...codeFromProp,
        maxHeight: expanded ? undefined : maxHeightCss,
        overflowY: expanded ? "visible" : "auto",
        overflowX: expanded ? "visible" : "auto",
        position: "relative",
      },
    };
  }, [stylesProp, maxHeightCss, expanded]);

  useEffect(() => {
    setExpanded(false);
  }, [codeContent, maxHeightCss]);

  useLayoutEffect(() => {
    if (!maxHeightCss || expanded) {
      setOverflowing(false);
      return;
    }
    const root = rootRef.current;
    if (!root) return;
    const codeEl = root.querySelector(`.${CODE_SCROLL_AREA_CLASS}`) as HTMLElement | null;
    if (!codeEl) return;

    const update = () => {
      setOverflowing(codeEl.scrollHeight > codeEl.clientHeight + 2);
    };

    update();
    const ro = new ResizeObserver(update);
    ro.observe(codeEl);
    return () => {
      ro.disconnect();
    };
  }, [maxHeightCss, expanded, codeContent]);

  const showBottomFade = Boolean(maxHeightCss && !expanded && overflowing);
  const canToggle = Boolean((!expanded && overflowing) || expanded);
  const showFoldBottom = Boolean(showBottomFade || canToggle);

  return {
    rootRef,
    expanded,
    setExpanded,
    mergedClassNames,
    mergedStyles,
    maxHeightCss,
    showFoldBottom,
    canToggle,
    showBottomFade,
  };
}
